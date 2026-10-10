#!/usr/bin/env bash
# Run in CodeArts Build/Deploy with obsutil configured through a protected identity.
set -euo pipefail
sha="${1:?full release SHA required}"
release_dir="${2:?release directory required}"
bucket="${3:?OBS bucket name required}"
h5_url="${4:?public HTTPS H5 URL required}"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ "$bucket" =~ ^[a-z0-9][a-z0-9.-]{2,62}$ ]] || exit 1
[[ "$h5_url" == https://* ]] || exit 1
command -v obsutil >/dev/null || { echo 'obsutil is required' >&2; exit 1; }

python3 - "$release_dir/release.json" "$release_dir/yunsync-h5.tar.gz" "$sha" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
if manifest.get('gitCommit') != sys.argv[3]:
    raise SystemExit('Release manifest commit mismatch')
with Path(sys.argv[2]).open('rb') as artifact:
    actual = hashlib.file_digest(artifact, 'sha256').hexdigest()
if actual != manifest['artifacts']['yunsync-h5.tar.gz']['sha256']:
    raise SystemExit('H5 artifact checksum mismatch')
PY

work="$(mktemp -d)"
backed_up=false
first_deploy="${YUNSYNC_FIRST_DEPLOY:-false}"
committed=false
index_attempted=false
cleanup() {
  status=$?
  if [[ "$status" -ne 0 && "$committed" == false ]]; then
    if [[ "$backed_up" == true ]]; then
      obsutil cp "$backup" "obs://$bucket/index.html" || true
    elif [[ "$first_deploy" == true && "$index_attempted" == true ]]; then
      obsutil rm "obs://$bucket/index.html" -f || true
    fi
  fi
  rm -rf -- "$work"
}
trap cleanup EXIT
tar -xzf "$release_dir/yunsync-h5.tar.gz" -C "$work"
[[ -f "$work/index.html" ]] || { echo 'H5 archive has no index.html' >&2; exit 1; }

# Keep the previous entry point; hashed assets are additive and survive rollback.
backup="obs://$bucket/.rollback/$sha/index.html"
if obsutil cp "obs://$bucket/index.html" "$backup"; then
  backed_up=true
elif [[ "$first_deploy" != true ]]; then
  echo 'Cannot back up existing H5 entry; set YUNSYNC_FIRST_DEPLOY=true only for an empty bucket' >&2
  exit 1
fi

while IFS= read -r -d '' file; do
  relative="${file#"$work"/}"
  obsutil cp "$file" "obs://$bucket/$relative"
done < <(find "$work" -type f ! -name index.html -print0)

index_attempted=true
obsutil cp "$work/index.html" "obs://$bucket/index.html"
if ! python3 - "$h5_url" "$sha" <<'PY'
import sys, urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=12) as response:
    assert response.status == 200
    assert 'text/html' in response.headers.get('Content-Type', '')
    assert f'<meta name="yunsync-release" content="{sys.argv[2]}">'.encode() in response.read(250_000)
PY
then
  echo 'H5 verification failed; restoring previous entry point' >&2
  exit 1
fi
committed=true
echo "Published H5 $sha"
