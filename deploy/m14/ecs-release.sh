#!/usr/bin/env bash
# Run as a privileged CodeArts Deploy host step after uploading the release bundle.
set -euo pipefail

sha="${1:?full release SHA required}"
release_dir="${2:?release directory required}"
api_url="${3:?public HTTPS API URL required}"
h5_url="${4:?public HTTPS H5 URL required}"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid release SHA' >&2; exit 1; }
[[ "$api_url" == https://* && "$h5_url" == https://* ]] || { echo 'Public URLs must use HTTPS' >&2; exit 1; }
[[ "$EUID" -eq 0 ]] || { echo 'Run through the CodeArts Deploy sudo option' >&2; exit 1; }

env_file=/etc/yunsync/api.env
upstream=/etc/nginx/snippets/yunsync-upstream.conf
state_dir=/var/lib/yunsync
[[ -f "$env_file" && -f "$upstream" ]] || { echo 'Host configuration is incomplete' >&2; exit 1; }
[[ "$(stat -c %a "$env_file")" == 600 ]] || { echo 'api.env must have mode 600' >&2; exit 1; }

python3 - "$release_dir/release.json" "$release_dir/yunsync-api.tar" "$sha" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
if manifest.get('gitCommit') != sys.argv[3]:
    raise SystemExit('Release manifest commit mismatch')
expected = manifest['artifacts']['yunsync-api.tar']['sha256']
with Path(sys.argv[2]).open('rb') as artifact:
    actual = hashlib.file_digest(artifact, 'sha256').hexdigest()
if actual != expected:
    raise SystemExit('API artifact checksum mismatch')
PY

mkdir -p "$state_dir"
active="$(cat "$state_dir/active-slot" 2>/dev/null || true)"
if [[ "$active" == blue ]]; then slot=green; port=18001; else slot=blue; port=18000; fi
container="yunsync-api-$slot"
previous_upstream="$(cat "$upstream")"
switched=false
committed=false
cleanup() {
  if [[ "$committed" == true ]]; then return; fi
  if [[ "$switched" == true ]]; then
    printf '%s\n' "$previous_upstream" > "$upstream"
    nginx -t >/dev/null 2>&1 && systemctl reload nginx || true
  fi
  docker rm -f "$container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker load -i "$release_dir/yunsync-api.tar" >/dev/null
docker image inspect "yunsync-api:$sha" >/dev/null
docker rm -f "$container" >/dev/null 2>&1 || true
docker run -d --name "$container" --restart unless-stopped \
  --env-file "$env_file" -e "YUNSYNC_RELEASE_SHA=$sha" \
  -p "127.0.0.1:$port:8000" "yunsync-api:$sha" >/dev/null

ready=false
for attempt in {1..30}; do
  if python3 - "$port" "$sha" <<'PY'
import json, sys, urllib.request
try:
    with urllib.request.urlopen(f'http://127.0.0.1:{sys.argv[1]}/health', timeout=2) as response:
        health = json.load(response)
    deps = health.get('dependencies', {})
    assert health.get('releaseSha') == sys.argv[2]
    assert deps.get('database', {}).get('kind') == 'postgresql'
    assert deps.get('database', {}).get('status') == 'ok'
    assert deps.get('cache', {}).get('backend') == 'redis'
    assert deps.get('cache', {}).get('status') == 'ok'
except Exception:
    sys.exit(1)
PY
  then ready=true; break; fi
  sleep 2
done
[[ "$ready" == true ]] || { echo 'Candidate failed RDS/DCS health gate' >&2; exit 1; }

tmp_upstream="$(mktemp "${upstream}.XXXXXX")"
printf 'proxy_pass http://127.0.0.1:%s;\n' "$port" > "$tmp_upstream"
chmod 644 "$tmp_upstream"
mv -f "$tmp_upstream" "$upstream"
switched=true
nginx -t >/dev/null
systemctl reload nginx

python3 "$release_dir/smoke.py" --api-base "$api_url" --h5-url "$h5_url" --expected-sha "$sha"
printf '%s\n' "$slot" > "$state_dir/active-slot"
printf '%s\n' "$sha" > "$state_dir/active-sha"
committed=true
echo "Released $sha on $slot; previous container retained for rollback"
