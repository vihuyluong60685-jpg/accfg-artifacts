#!/usr/bin/env bash
# Inside the pinned image; stdin is the pinned SNAX source archive.
set -euo pipefail
src="$(mktemp -d)"
cd "$src"
tar -xf -
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$src"
cd kernels/streamer_matmul
cp /pilot/cases/partial{.mk,_harness.c} .
for spec in "$@"; do
  IFS=: read -r method k steps dma seed repeat <<< "$spec"
  dest="/out/partial/${method}_k${k}_t${steps}_d${dma}_s${seed}_r${repeat}"
  mkdir -p "$dest"
  if test -f "$dest/DONE"; then continue; fi
  work="$(mktemp -d)"
  {
    set -x
    start_ns="$(date +%s%N)"
    python3 /pilot/scripts/emit_fixture.py "$method" /pilot/cases/partial_schedule.mlir.in "$dest/input.mlir"
    pipeline=insert-accfg-op{accelerator=snax_gemm}
    if [[ "$method" == W ]]; then pipeline+=,accfg-config-overlap; fi
    ../../compiler/snax-opt -p "$pipeline" "$dest/input.mlir" -o "$dest/scheduled.mlir"
    ../../compiler/snax-opt -p convert-accfg-to-csr "$dest/scheduled.mlir" -o pilot.snax-opt.mlir
    cp pilot.snax-opt.mlir "$dest/lowered.mlir"
    rm -f partial_harness.o pilot.o pilot.{x,postproc.mlir,ll.mlir,ll,ll12}
    if [[ "$repeat" == 1 ]]; then
      make -j1 -f partial.mk pilot.x "K=$k" "STEPS=$steps" "DMA=$dma" "SEED=$seed"
      cp pilot.x "$dest/pilot.x"
      printf '%s\n' "$(( ($(date +%s%N) - start_ns) / 1000000 ))" > "$dest/build_ms"
    else
      previous="${dest%_r*}_r1"
      cp "$previous/pilot.x" "$dest/pilot.x"
      cp "$previous/build_ms" "$dest/"
    fi
    sha256sum "$dest/pilot.x" > "$dest/elf.sha256"
    wc -c < "$dest/pilot.x" > "$dest/elf.bytes"
    llvm-objdump-17 -d "$dest/pilot.x" > "$dest/disassembly.txt"
    simulator=/opt/snax-streamer-gemm-rtl/bin/snitch_cluster.vlt
    sim_rc=0
    (cd "$work" && timeout 60s "$simulator" "$dest/pilot.x") > "$dest/simulation.txt" 2>&1 || sim_rc=$?
    printf '%s\n' "$sim_rc" > "$dest/sim_exit"
    if [[ "$sim_rc" -eq 0 ]]; then
      for hart in 00000 00001; do
        name="trace_hart_$hart"
        spike-dasm < "$work/logs/$name.dasm" | /opt/gen_trace.py --permissive -d "$dest/$name.trace.json" | gzip -n > "$dest/$name.trace.txt.gz"
      done
      touch "$dest/DONE"
    fi
  } > "$dest/commands.log" 2>&1
  printf '%s exit=%s\n' "$spec" "$sim_rc"
  rm -r "$work"
done
