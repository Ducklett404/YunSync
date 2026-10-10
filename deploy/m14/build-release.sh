#!/usr/bin/env bash
# CodeArts Build entrypoint. The checkout commit is the release identity.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
release_sha="$(git rev-parse --verify HEAD)"
[[ "$release_sha" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid Git commit ID' >&2; exit 1; }
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo 'Tracked checkout has local changes; release must use an exact commit' >&2
  exit 1
fi

: "${VITE_YUNSYNC_API_BASE_URL:?Set the public HTTPS API URL in CodeArts Build variables}"
[[ "$VITE_YUNSYNC_API_BASE_URL" == https://* ]] || { echo 'API URL must use HTTPS' >&2; exit 1; }
export VITE_DATA_MODE=demo

npm --prefix miniapp ci
npm --prefix miniapp run type-check
for milestone in m2 m3 m4 m5 m6; do
  npm --prefix miniapp run "validate:$milestone"
done
npm --prefix miniapp run build:h5

RELEASE_SHA="$release_sha" python3 - <<'PY'
import os
from pathlib import Path
index = Path('miniapp/dist/build/h5/index.html')
html = index.read_text(encoding='utf-8')
assert '</head>' in html, 'H5 index has no head section'
html = html.replace('</head>', f'<meta name="yunsync-release" content="{os.environ["RELEASE_SHA"]}"></head>', 1)
index.write_text(html, encoding='utf-8')
PY

python3 -m venv .m14-venv
.m14-venv/bin/python -m pip install -r backend/requirements-dev.txt
(cd backend && ../.m14-venv/bin/python -m pytest -q)

docker build -f backend/Dockerfile -t "yunsync-api:$release_sha" .
mkdir -p deploy/m14/out
docker save -o deploy/m14/out/yunsync-api.tar "yunsync-api:$release_sha"
tar -C miniapp/dist/build/h5 -czf deploy/m14/out/yunsync-h5.tar.gz .
cp deploy/m14/smoke.py deploy/m14/ecs-release.sh deploy/m14/rollback-api.sh \
  deploy/m14/publish-h5.sh deploy/m14/rollback-h5.sh deploy/m14/deploy-release.sh \
  deploy/m14/out/

RELEASE_SHA="$release_sha" .m14-venv/bin/python - <<'PY'
import hashlib
import json
import os
from pathlib import Path

out = Path('deploy/m14/out')
artifacts = {}
for name in ('yunsync-api.tar', 'yunsync-h5.tar.gz'):
    path = out / name
    digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
    artifacts[name] = {'sha256': digest, 'bytes': path.stat().st_size}
(out / 'release.json').write_text(json.dumps({
    'schemaVersion': 1,
    'gitCommit': os.environ['RELEASE_SHA'],
    'artifacts': artifacts,
}, indent=2) + '\n', encoding='utf-8')
PY
printf 'Built release %s\n' "$release_sha"
