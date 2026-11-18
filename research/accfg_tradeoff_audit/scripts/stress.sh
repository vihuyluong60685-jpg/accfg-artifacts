#!/usr/bin/env bash
set -euo pipefail
kit="$(mktemp -d)"
git -c safe.directory='*' -C /accepted/snax-mlir archive 0df8b515768232036bceb6af7a6d5935b5e1a3db | tar -xf - -C "$kit"
export PYTHONPATH="$kit"
mkdir -p /out/stress
cd /out/stress
for copies in 1 8 32; do
 for mode in A D; do
  rc=0
  (set -x; python3 /audit/scripts/structure_stress.py /out/compile/no_copy_16x16x16_A_r1/preopt.mlir "$copies" "$mode") \
     > "${copies}_$mode.json" 2> "${copies}_$mode.log" || rc=$?
  printf '%s\n' "$rc" > "${copies}_$mode.exit"
 done
done
