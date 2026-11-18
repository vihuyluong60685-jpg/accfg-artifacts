#!/usr/bin/env bash
set -euo pipefail
out=/out/elf
mkdir -p "$out"
exec > "$out/commands.log" 2>&1
set -x
llvm-objdump-17 --version
for f in /accepted/snax-mlir/kernels/streamer_matmul/results/*/*/generated.stream.x; do
  name="$(basename "$(dirname "$f")")"
  id="original_$name"
  llvm-objdump-17 -d --disassemble-symbols=streamer_matmul,_mlir_ciface_streamer_matmul,streamer_matmul_pinned,streamer_matmul_pinned_1,_mlir_ciface_streamer_matmul_pinned,_mlir_ciface_streamer_matmul_pinned_1 "$f" > "$out/$id.txt"
done
for f in /out/{extras,envelope,compile}/*/pilot.x; do
  id="$(basename "$(dirname "$(dirname "$f")")")_$(basename "$(dirname "$f")")"
  llvm-objdump-17 -d --disassemble-symbols=streamer_matmul,_mlir_ciface_streamer_matmul,streamer_matmul_pinned,streamer_matmul_pinned_1,_mlir_ciface_streamer_matmul_pinned,_mlir_ciface_streamer_matmul_pinned_1 "$f" > "$out/$id.txt"
done
printf '0\n' > "$out/objdump.exit"
