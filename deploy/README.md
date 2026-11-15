# Deploy (systemd --user)

Reference copies of the units that run the live demo on the VM. Paths assume `/home/ubuntu/projects/socialnet-bot-tracker`.

| unit | what |
|---|---|
| `headcount-api.service` | uvicorn on 127.0.0.1:8000 (`MemoryMax=2500M`) |
| `headcount-photon.service` | iMessage poller (`src.messaging.photon_service`), logs a heartbeat every 5 min |
| `headcount-tunnel.service` | cloudflared quick tunnel to the API |
| `headcount-watchdog.timer` / `.service` | every 2 min runs `deploy/watchdog.sh` |

## Install

```
cp deploy/systemd/* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now headcount-api headcount-photon headcount-tunnel headcount-watchdog.timer
loginctl enable-linger $USER   # keep them running after logout
```

## Restart

```
systemctl --user restart headcount-api      # then wait ~40 s for /health warm.live and warm.news
systemctl --user restart headcount-photon   # after the API, never before it is warm
journalctl --user -u headcount-api -n 50    # logs also in data/processed/{api,photon,tunnel_api,watchdog}.log
```

## The tunnel: do not restart it casually

A quick tunnel gets a **new public URL on every restart**, and the deployed site (demoyk.com) is built against the old one.
After any tunnel restart:

1. read the new URL: `grep -o 'https://[a-z-]*\.trycloudflare\.com' data/processed/tunnel_api.log | tail -1`
2. set `PUBLIC_API_BASE=<new url>` in `.env`
3. `web/app/deploy-vercel.sh <new url>`

The watchdog restarts only the API and the poller. If the tunnel is unhealthy it logs `TUNNEL UNHEALTHY` to `data/processed/watchdog.log` and does nothing else.

## Abuse limits (src/api/limits.py)

`/claim` and `/agent`: 10 requests/min per client IP (`CF-Connecting-IP`; loopback without that header, i.e. the local poller, is exempt).
`/join`: 3 POSTs/hour per IP. Claims capped at 400 chars, agent messages at 600; at most 3 analyses run at once (503 "busy" after 60 s).
