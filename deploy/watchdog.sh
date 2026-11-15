#!/usr/bin/env bash
# Headcount watchdog: restarts the API / poller when unhealthy. NEVER restarts the tunnel (its URL would change
# and demoyk.com would need a redeploy); an unhealthy tunnel is only logged loudly.
# Run by headcount-watchdog.timer every 2 min. Log: data/processed/watchdog.log
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG="$ROOT/data/processed/watchdog.log"
PHOTON_LOG="$ROOT/data/processed/photon.log"
STALE_SECONDS=${STALE_SECONDS:-720}   # heartbeat every 5 min; allow two missed beats plus slack
log() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }

PUBLIC_API_BASE="$(grep -E '^PUBLIC_API_BASE=' "$ROOT/.env" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"'"'"' ')"

if ! curl -fsS -m 8 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  # a freshly started API needs ~40 s to load; skip if it was (re)started under 90 s ago
  age=$(( $(date +%s) - $(date -d "$(systemctl --user show headcount-api -p ActiveEnterTimestamp --value)" +%s 2>/dev/null || echo 0) ))
  if [ "$age" -lt 90 ]; then
    log "api: not healthy yet, started ${age}s ago, waiting"
  else
    log "api: /health failed -> restarting headcount-api"
    systemctl --user restart headcount-api
  fi
fi

state="$(systemctl --user is-active headcount-photon)"
if [ "$state" != "active" ] && [ "$state" != "activating" ]; then
  log "photon: unit not active -> restarting headcount-photon"
  systemctl --user restart headcount-photon
elif [ -f "$PHOTON_LOG" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$PHOTON_LOG") ))
  if [ "$age" -gt "$STALE_SECONDS" ]; then
    log "photon: log stale ${age}s -> restarting headcount-photon"
    systemctl --user restart headcount-photon
  fi
fi

if [ -n "$PUBLIC_API_BASE" ] && ! curl -fsS -m 10 "$PUBLIC_API_BASE/health" >/dev/null 2>&1; then
  log "!!! TUNNEL UNHEALTHY: $PUBLIC_API_BASE/health failed. NOT restarting it. If the URL changed: web/app/deploy-vercel.sh <new url> and update PUBLIC_API_BASE in .env"
fi
exit 0
