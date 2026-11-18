#!/usr/bin/env bash
# Exercise the pinned 8x8 schedule matcher on released AD01 input shapes.
set -euo pipefail
kit="$(mktemp -d)"
tar -xf - -C "$kit"
export PYTHONPATH="$kit"
for name in native_ad01 native_ad01_batch1; do
  cd "/out/$name"
  rc=0
  (
    set -x
    timeout 40s "$kit/compiler/snax-opt" -p 'insert-accfg-op{accelerator=snax_gemm},dispatch-kernels,guarded-linalg-to-memref-stream,schedule-memref-linalg,stream-snaxify,convert-linalg-to-accfg' \
      ad01.bufferized.mlir -o ad01.scheduled-native.mlir
  ) > scheduling.log 2>&1 || rc=$?
  printf '%s\n' "$rc" > scheduling.exit
  printf '%s template scheduling exit %s\n' "$name" "$rc"
done
