#!/usr/bin/env bash
set -euo pipefail
kit="$(mktemp -d)"
tar -xf - -C "$kit"
export PYTHONPATH="$kit"
cd "$kit/kernels/streamer_matmul"
cp /gate/cases/{gate.mk,workload.c} .
session="${1:-matrix}"
for graph in mobile attention; do
  case "$session" in
    smoke) methods=(A C);;
    waves) methods=(C M0);;
    matrix) methods=(A B C M0 M1 M2 M3 M4 M5 M6);;
    *) exit 2;;
  esac
  for method in "${methods[@]}"; do
    dir="/out/$graph/$method"
    mkdir -p "$dir"
    if [[ "$session" = waves ]]; then
      status=0
      bash /gate/scripts/execute.sh "$dir" wave || status=$?
      printf '%s %s wave exit %s\n' "$graph" "$method" "$status"
      continue
    fi
    if [[ ! -f "$dir/BUILT" ]]; then
      status=0
      bash -euo pipefail -c '
        set -x
        graph="$1"; method="$2"; dir="$3"
        if [[ "$method" == M* ]]; then
          origin="/out/$graph/C"
          test -e "$origin/BUILT"
          python3 /gate/scripts/permute.py "$origin/gate.x" "$origin/disassembly.txt" "$dir/gate.x" "$dir/patch.json" "${method#M}"
        else
          python3 /gate/scripts/generate.py "$graph" "$dir/base.mlir" gate_fixtures.h "$dir/golden.json"
          cp gate_fixtures.h "$dir"
          phases="insert-accfg-op{accelerator=snax_gemm}"
          [[ "$method" == A ]] || phases+=",accfg-dedup"
          [[ "$method" != C ]] || phases+=",accfg-config-overlap"
          ../../compiler/snax-opt -p "$phases" "$dir/base.mlir" -o "$dir/scheduled.mlir"
          ../../compiler/snax-opt -p convert-accfg-to-csr "$dir/scheduled.mlir" -o gates.snax-opt.mlir
          cp gates.snax-opt.mlir "$dir/lowered.mlir"
          rm -f gates.{o,postproc.mlir,ll.mlir,ll,ll12} workload.o gate.x
          mobile=0
          [[ "$graph" != mobile ]] || mobile=1
          make -j1 -f gate.mk gate.x MOBILE="$mobile"
          cp gate.x "$dir/"
        fi
        llvm-objdump-17 -d "$dir/gate.x" > "$dir/disassembly.txt"
        sha256sum "$dir/gate.x" > "$dir/elf.sha256"
        touch "$dir/BUILT"
      ' _ "$graph" "$method" "$dir" > "$dir/build.log" 2>&1 || status=$?
      printf '%s\n' "$status" > "$dir/build.exit"
      printf '%s %s build exit %s\n' "$graph" "$method" "$status"
      if [[ "$status" != 0 ]]; then continue; fi
    fi
    status=0
    bash /gate/scripts/execute.sh "$dir" || status=$?
    printf '%s %s trace exit %s\n' "$graph" "$method" "$status"
  done
done
