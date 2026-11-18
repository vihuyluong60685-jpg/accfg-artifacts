#!/usr/bin/env bash
set -euo pipefail
kit="$(mktemp -d)"
git -c safe.directory='*' -C /accepted/snax-mlir archive 0df8b515768232036bceb6af7a6d5935b5e1a3db | tar -xf - -C "$kit"
export PYTHONPATH="$kit"
cd "$kit/kernels/streamer_matmul"
kind="$1"
if [[ "$kind" == compile ]]; then
  scopes=(no_copy)
  shapes=(16x16x16 128x128x128 512x512x512)
  sequences=(ABCD BCDA CDAB DABC)
elif [[ "$kind" == extras ]]; then
  scopes=(no_copy checked)
  shapes=(8x8x8 20x20x20 24x24x24 24x16x32 40x40x40)
  sequences=(ABCD)
else
  scopes=(checked)
  shapes=(16x16x16)
  sequences=(ABCD)
  # Add a common outer pair of marker reads, independent of the inner IR pair.
  python3 /audit/scripts/outer_markers.py main.c
fi
for shape in "${shapes[@]}"; do
 IFS=x read -r n k m <<< "$shape"
 for scope in "${scopes[@]}"; do
  rep=0
  for sequence in "${sequences[@]}"; do
   rep=$((rep+1))
   for ((idx=0; idx<${#sequence}; idx++)); do
    method="${sequence:idx:1}"
    job="/out/$kind/${scope}_${shape}_${method}_r$rep"
    if [[ -f "$job/DONE" ]]; then continue; fi
    if [[ "$method" != A && "$kind" == extras && -f "/out/$kind/${scope}_${shape}_A_r1/build.exit" ]]; then
      [[ "$(cat "/out/$kind/${scope}_${shape}_A_r1/build.exit")" == 0 ]] || continue
    fi
    mkdir -p "$job"
    case "$method" in
      A) flag=NO_ACCFG_OPT=1;; B) flag=DEDUP_ONLY=1;; C) flag=OVERLAP_ONLY=1;; D) flag=ACCFG_BOTH=1;;
    esac
    rm -f generated.* data.c data.h main.o data.o
    flags=("$flag")
    [[ "$scope" == checked ]] || flags+=(NO_CHECK=1)
    rc=0
    (
      set -x
      python3 - "$n" "$k" "$m" <<'PY'
import sys
from genbenchmark import create_tiled_matrix_multiply, write_module_to_file
from gendata import create_test_data
n,k,m=map(int,sys.argv[1:])
write_module_to_file(create_tiled_matrix_multiply(n,k,m,[8,8]),"generated.transform.mlir")
create_test_data(n=n,m=m,k=k)
PY
    ) > "$job/input.log" 2>&1
    printf '%s\n' "$((idx+1))" > "$job/order"
    python3 /audit/scripts/process_metrics.py "$job/build.json" make -j1 generated.stream.x "${flags[@]}" \
      "SIZE_N=$n" "SIZE_K=$k" "SIZE_M=$m" > "$job/build.log" 2>&1 || rc=$?
    printf '%s\n' "$rc" > "$job/build.exit"
    for file in generated.*mlir; do cp "$file" "$job/"; done
    if [[ "$rc" == 0 ]]; then
      if [[ "$kind" == compile ]]; then
        if [[ "$rep" == 1 ]]; then
          cp generated.stream.x "$job/pilot.x"
          python3 /audit/scripts/pass_driver.py "$job" "${flags[@]}" > "$job/pass_prepare.log" 2>&1 || rc=$?
          printf '%s\n' "$rc" > "$job/prepare.exit"
        fi
      else
        cp generated.stream.x "$job/pilot.x"
        bash /audit/scripts/rtl.sh "$job" trace || rc=$?
        if [[ "$kind" == envelope && ("$method" == B || "$method" == D) && "$rc" == 0 ]]; then
          bash /audit/scripts/rtl.sh "$job" wave || rc=$?
        fi
      fi
    fi
    printf '%s %s %s %s status %s\n' "$kind" "$scope" "$shape" "$method/$rep" "$rc"
    touch "$job/DONE"
   done
  done
 done
done
