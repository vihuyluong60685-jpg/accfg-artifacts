#!/usr/bin/env bash
set -euo pipefail
stage="$(mktemp -d)"
cd "$stage"
tar -xf -
export PYTHONPATH="$stage" PYTHONDONTWRITEBYTECODE=1
out=/out/policy_ir
mkdir -p "$out"
python3 /pilot/scripts/emit_fixture.py S /pilot/cases/partial_schedule.mlir.in "$out/input.mlir"
python3 /pilot/scripts/emit_fixture.py G /pilot/cases/partial_schedule.mlir.in "$out/partial.input.mlir"
base=insert-accfg-op{accelerator=snax_gemm}
for method in base dedup overlap both partial; do
  flags="$base"
  input="$out/input.mlir"
  case "$method" in
    dedup) flags+=,accfg-dedup;;
    overlap) flags+=,accfg-config-overlap;;
    both) flags+=,accfg-dedup,accfg-config-overlap;;
    partial) input="$out/partial.input.mlir";;
  esac
  ./compiler/snax-opt -p "$flags" "$input" -o "$out/$method.mlir"
  ./compiler/snax-opt -p convert-accfg-to-csr "$out/$method.mlir" -o "$out/$method.lowered.mlir"
done
for method in dedup overlap both; do
  cmp "$out/base.lowered.mlir" "$out/$method.lowered.mlir"
  echo "identical lowered IR: $method"
done
sha256sum "$out"/*.lowered.mlir
