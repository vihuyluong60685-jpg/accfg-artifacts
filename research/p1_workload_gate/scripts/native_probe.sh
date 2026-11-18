#!/usr/bin/env bash
# A bounded compilation probe of the official MLCommons AD01 artifact.
set -eo pipefail
kit="$(mktemp -d)"
tar -xf - -C "$kit"
mode="${1:-native_ad01}"
cd "/out/$mode"
set -x
test "$(od -An -tc -N4 -j4 ad01_int8.tflite | tr -d ' \n')" = TFL3
rc=0
TF_CPP_MIN_LOG_LEVEL=2 OMP_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 \
  timeout 45s python3 "$kit/runtime/tflite_to_tosa.py" -c ad01_int8.tflite -o ad01.tosa.mlir.bc || rc=$?
printf '%s\n' "$rc" > conversion.exit
if [[ "$rc" != 0 ]]; then exit "$rc"; fi
timeout 30s mlir-opt-17 --allow-unregistered-dialect --mlir-print-op-generic ad01.tosa.mlir.bc -o ad01.tosa.mlir
export PYTHONPATH="$kit"
source_ir=ad01.tosa.mlir
if [[ "$mode" == native_ad01_batch1 ]]; then
  sed 's/tensor<?x/tensor<1x/g' ad01.tosa.mlir > ad01.batch1.mlir
  source_ir=ad01.batch1.mlir
fi
rc=0
timeout 40s mlir-opt-17 --pass-pipeline='builtin.module(func.func(tosa-to-linalg-named, tosa-to-tensor, tosa-to-linalg))' --mlir-print-op-generic "$source_ir" -o ad01.tensor.mlir || rc=$?
if [[ "$rc" == 0 ]]; then
  timeout 40s mlir-opt-17 --tosa-to-arith=include-apply-rescale --linalg-generalize-named-ops \
    --empty-tensor-to-alloc-tensor --one-shot-bufferize='bufferize-function-boundaries allow-return-allocs function-boundary-type-conversion=identity-layout-map' \
    --mlir-print-op-generic ad01.tensor.mlir -o ad01.bufferized.mlir || rc=$?
fi
printf '%s\n' "$rc" > bufferize.exit
if [[ "$rc" != 0 ]]; then exit "$rc"; fi
rc=0
timeout 40s "$kit/compiler/snax-opt" -p 'insert-accfg-op{accelerator=snax_gemm},dispatch-kernels,guarded-linalg-to-memref-stream,stream-snaxify,convert-linalg-to-accfg' ad01.bufferized.mlir -o ad01.dispatch.mlir || rc=$?
printf '%s\n' "$rc" > dispatch.exit
exit "$rc"
