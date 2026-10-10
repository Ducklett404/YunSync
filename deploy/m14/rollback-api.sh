#!/usr/bin/env bash
set -euo pipefail
[[ "$EUID" -eq 0 ]] || { echo 'Run as root' >&2; exit 1; }
api_url="${1:?public HTTPS API URL required}"
h5_url="${2:?public HTTPS H5 URL required}"
[[ "$api_url" == https://* && "$h5_url" == https://* ]] || exit 1
state_dir=/var/lib/yunsync
upstream=/etc/nginx/snippets/yunsync-upstream.conf
active="$(cat "$state_dir/active-slot")"
if [[ "$active" == blue ]]; then slot=green; port=18001; else slot=blue; port=18000; fi
candidate="yunsync-api-$slot"
docker inspect "$candidate" >/dev/null
sha="$(python3 - "$port" <<'PY'
import json, sys, urllib.request
with urllib.request.urlopen(f'http://127.0.0.1:{sys.argv[1]}/health', timeout=5) as response:
    health = json.load(response)
print(health.get('releaseSha', ''))
PY
)"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'No healthy previous release found' >&2; exit 1; }
python3 - "$port" "$sha" <<'PY'
import json, sys, urllib.request
with urllib.request.urlopen(f'http://127.0.0.1:{sys.argv[1]}/health', timeout=5) as response:
    health = json.load(response)
assert health.get('releaseSha') == sys.argv[2]
assert health.get('dependencies', {}).get('database', {}).get('status') == 'ok'
assert health.get('dependencies', {}).get('cache', {}).get('status') == 'ok'
PY
previous="$(cat "$upstream")"
printf 'proxy_pass http://127.0.0.1:%s;\n' "$port" > "$upstream"
if ! nginx -t >/dev/null || ! systemctl reload nginx || ! python3 "$(dirname "$0")/smoke.py" --api-base "$api_url" --h5-url "$h5_url" --expected-sha "$sha"; then
  printf '%s\n' "$previous" > "$upstream"
  nginx -t >/dev/null && systemctl reload nginx
  echo 'Rollback target failed verification; current release restored' >&2
  exit 1
fi
printf '%s\n' "$slot" > "$state_dir/active-slot"
printf '%s\n' "$sha" > "$state_dir/active-sha"
echo "Rolled back API to $sha"
