#!/usr/bin/env bash
# Run inside the official Docker image with compiler source archive on stdin.
set -euo pipefail
compiler="$(mktemp -d)"
tar -xf - -C "$compiler"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$compiler"
cd "$compiler/kernels/streamer_matmul"
cp /v2/cases/{chain.mk,tensor_chain.c} .
if [[ "$#" == 0 ]]; then mapfile -t specs < /v2/configs/chain_specs.txt; else specs=("$@"); fi
for spec in "${specs[@]}"; do
  IFS=: read -r scenario method k trips bytes seed wave <<< "$spec"
  key="c${scenario}_${method}_k${k}_t${trips}_b${bytes}_s${seed}"
  job="/out/chain/$key"
  mkdir -p "$job"
  if [[ ! -f "$job/BUILT" ]]; then
    status=0
    bash -euo pipefail -c '
      set -x
      scenario="$1"; method="$2"; k="$3"; trips="$4"; bytes="$5"; seed="$6"; job="$7"
      if [[ "$method" == l ]]; then
        g="${job/_l_/_g_}"
        test -f "$g/BUILT"
        python3 /v2/scripts/late_chain_elf.py "$g/pilot.x" "$g/disassembly.txt" "$job/pilot.x" "$job/patch.json" "$scenario"
        printf "%s\n" "$g" > "$job/source_path"
      else
        start=$(date +%s%N)
        ir_method="$method"
        [[ "$method" != w ]] || ir_method=s
        python3 /v2/scripts/emit_chain.py /v2/cases/tensor_chain.mlir.in "$job/input.mlir" chain_golden.h "$k" "$seed" "$scenario" "$ir_method"
        cp chain_golden.h "$job/"
        pipeline="insert-accfg-op{accelerator=snax_gemm}"
        [[ "$method" != w ]] || pipeline+=",accfg-config-overlap"
        ../../compiler/snax-opt -p "$pipeline" "$job/input.mlir" -o "$job/scheduled.mlir"
        ../../compiler/snax-opt -p convert-accfg-to-csr "$job/scheduled.mlir" -o chain.snax-opt.mlir
        cp chain.snax-opt.mlir "$job/lowered.mlir"
        rm -f chain.o tensor_chain.o chain.{x,postproc.mlir,ll.mlir,ll,ll12}
        make -j1 -f chain.mk chain.x "K=$k" "STEPS=$trips" "DMA=$bytes" "SEED=$seed" "SCENARIO=$scenario"
        cp chain.x "$job/pilot.x"
        printf "%s\n" "$(( ($(date +%s%N)-start)/1000000 ))" > "$job/build_ms"
      fi
      sha256sum "$job/pilot.x" > "$job/elf.sha256"
      llvm-objdump-17 -d "$job/pilot.x" > "$job/disassembly.txt"
      touch "$job/BUILT"
    ' _ "$scenario" "$method" "$k" "$trips" "$bytes" "$seed" "$job" > "$job/build.log" 2>&1 || status=$?
    printf '%s\n' "$status" > "$job/build_exit"
    printf '%s build exit %s\n' "$spec" "$status"
    if [[ "$status" != 0 ]]; then continue; fi
  fi
  status=0
  bash /v2/scripts/execute.sh "$job" || status=$?
  printf '%s trace exit %s\n' "$spec" "$status"
  if [[ "$wave" == 1 && "$status" == 0 ]]; then
    bash /v2/scripts/execute.sh "$job" wave || status=$?
    printf '%s wave exit %s\n' "$spec" "$status"
  fi
done
