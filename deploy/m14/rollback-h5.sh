#!/usr/bin/env bash
set -euo pipefail
failed_sha="${1:?failed release SHA required}"
bucket="${2:?OBS bucket name required}"
[[ "$failed_sha" =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ "$bucket" =~ ^[a-z0-9][a-z0-9.-]{2,62}$ ]] || exit 1
obsutil cp "obs://$bucket/.rollback/$failed_sha/index.html" "obs://$bucket/index.html"
echo "Restored previous H5 entry point from backup for $failed_sha"
