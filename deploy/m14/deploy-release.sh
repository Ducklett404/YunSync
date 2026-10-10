#!/usr/bin/env bash
# One CodeArts Deploy host step: publish H5, release API, restore H5 on any API failure.
set -euo pipefail
sha="${1:?full release SHA required}"
release_dir="${2:?release directory required}"
bucket="${3:?OBS bucket required}"
api_url="${4:?public HTTPS API URL required}"
h5_url="${5:?public HTTPS H5 URL required}"
bash "$release_dir/publish-h5.sh" "$sha" "$release_dir" "$bucket" "$h5_url"
if ! bash "$release_dir/ecs-release.sh" "$sha" "$release_dir" "$api_url" "$h5_url"; then
  bash "$release_dir/rollback-h5.sh" "$sha" "$bucket" || {
    echo 'API rollback ran, but H5 rollback needs operator attention' >&2
  }
  exit 1
fi
echo "M14 release $sha passed public smoke checks"
