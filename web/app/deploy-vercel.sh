#!/usr/bin/env bash
# Deploy the web app to https://demoyk.com (Vercel project "headcount", account ik301s-projects).
# The API stays on the VM behind a Cloudflare tunnel; pass its URL so the static site knows where to call.
#   web/app/deploy-vercel.sh https://<api-tunnel>.trycloudflare.com
# When the API tunnel URL changes, rerun this. Links in text replies come from DASHBOARD_BASE in .env.
set -euo pipefail
API="${1:?usage: deploy-vercel.sh <api base url>}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${OUT:-$HOME/projects/headcount-deploy}"
cd "$HERE"
VITE_API_BASE="$API" node node_modules/vite/bin/vite.js build --outDir "$OUT" --emptyOutDir
cat > "$OUT/vercel.json" <<'EOF'
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }],
  "headers": [{ "source": "/site_data.json", "headers": [{ "key": "Cache-Control", "value": "public, max-age=60" }] }]
}
EOF
cd "$OUT"
npx -y vercel@latest deploy --prod --yes --name headcount
for u in / /story /challenge; do curl -s -o /dev/null -w "$u %{http_code}\n" "https://demoyk.com$u"; done
