#!/usr/bin/env bash
# Host entry point. Run from the P1 worktree root.
set -euo pipefail
stage="$PWD/research/p1_criticalpath_pilot"
original="${ACCFG_ACCEPTED_REPO:-/home/yanmo/research/projects/accfg-artifacts}"
image="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["docker"])' "$stage/configs/frozen_baseline.json")"
compiler=0df8b515768232036bceb6af7a6d5935b5e1a3db
test "$(git -C "$original/snax-mlir" rev-parse HEAD)" = "$compiler"
mkdir -p "$stage/local"
git -C "$original/snax-mlir" archive "$compiler" |
  docker run --rm -i --memory 3g --user "$(id -u):$(id -g)" \
    -v "$stage:/pilot:ro" -v "$stage/local:/out" -v "$original:/accepted:ro" \
    --entrypoint bash "$image" "/pilot/scripts/$1" "${@:2}"
