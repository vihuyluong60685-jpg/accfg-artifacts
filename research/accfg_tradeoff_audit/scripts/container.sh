#!/usr/bin/env bash
set -euo pipefail
audit="$PWD/research/accfg_tradeoff_audit"
source_repo="${ACCFG_BASE_CHECKOUT:-/home/yanmo/research/projects/accfg-artifacts}"
image="$(python3 -c 'import json;print(json.load(open("reports/configs/experiment_run.json"))["image"])')"
test "$(git -C "$source_repo" rev-parse HEAD)" = cbf660f1cc73dfffd589541c9c382b346a7206fd
docker run --rm -i --memory 3g --user "$(id -u):$(id -g)" -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$audit:/audit:ro" -v "$audit/local:/out" -v "$source_repo:/accepted:ro" \
  --entrypoint bash "$image" "/audit/scripts/$1" "${@:2}"
