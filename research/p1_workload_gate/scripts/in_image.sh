#!/usr/bin/env bash
set -euo pipefail
stage="$PWD/research/p1_workload_gate"
accepted="${ACCFG_ACCEPTED_REPO:-/home/yanmo/research/projects/accfg-artifacts}"
previous="${GATE_V2_CHECKOUT:-/home/yanmo/research/projects/accfg-p1-ablation}"
image="$(python3 -c 'import json;print(json.load(open("research/p1_criticalpath_pilot/configs/frozen_baseline.json"))["docker"])')"
test "$(git -C "$previous" rev-parse HEAD)" = 289979d8491e6554a6a07a83a31193e78bfc100a
mkdir -p "$stage/local"
docker run --rm -i --memory 3g --user "$(id -u):$(id -g)" \
  -e MPLCONFIGDIR=/tmp/mpl -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$stage:/gate:ro" -v "$stage/local:/out" -v "$PWD/research:/research:ro" \
  -v "$accepted:/accepted:ro" -v "$previous:/v2:ro" \
  --entrypoint bash "$image" "/gate/scripts/$1" "${@:2}"
