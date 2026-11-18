#!/usr/bin/env bash
# From the v2 worktree. Only the v2 local directory is mounted writable.
set -euo pipefail
stage="$PWD/research/p1_ablation_v2"
p1="${P1_CHECKOUT:-/home/yanmo/research/projects/accfg-p1-pilot}"
accepted="${ACCFG_ACCEPTED_REPO:-/home/yanmo/research/projects/accfg-artifacts}"
compiler=0df8b515768232036bceb6af7a6d5935b5e1a3db
image="$(python3 -c 'import json; print(json.load(open("research/p1_criticalpath_pilot/configs/frozen_baseline.json"))["docker"])')"
test "$(git -C "$p1" rev-parse HEAD)" = 75e16e3be1dbbe08280d1e22330dacafe477d17a
git -C "$accepted/snax-mlir" cat-file -e "$compiler^{commit}"
mkdir -p "$stage/local"
docker run --rm -i --memory 3g --user "$(id -u):$(id -g)" \
  -v "$stage:/v2:ro" -v "$stage/local:/out" -v "$p1:/p1:ro" \
  -v "$accepted:/accepted:ro" --entrypoint bash "$image" "/v2/scripts/$1" "${@:2}"
