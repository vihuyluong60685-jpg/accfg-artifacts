#!/usr/bin/env bash
set -euo pipefail
kit="$(mktemp -d)"
archive() { git -c safe.directory='*' -C "/accepted/$1" archive "$2" | tar -x -C "$3"; }
mkdir -p "$kit"/{gem,snax}
archive snax-mlir 0df8b515768232036bceb6af7a6d5935b5e1a3db "$kit/snax"
archive gemmini-rocc-tests 4fec505cadacec4c371305b90973fa18758e9ac0 "$kit/gem"
archive gemmini-rocc-tests/riscv-tests c84daca8824635b7d896003c78f9c6245997cf7a "$kit/gem/riscv-tests"
archive gemmini-rocc-tests/riscv-tests/env 0666378f353599d01fc48562b431b1dd049faab5 "$kit/gem/riscv-tests/env"
archive gemmini-rocc-tests/rocc-software fddb795a0b52e82f8f4ce9ead9b1428440a62ab0 "$kit/gem/rocc-software"
export PYTHONPATH="$kit/snax"
cd "$kit/gem/bareMetalMLIR"
# Both modes use the exact original optimized frontend and identical C/LLVM flags.
# Make a research-only rule around an already lowered, common-pipeline object.
sed 's/-DCHECK_RESULT=0/-DCHECK_RESULT=$(CHECK)/g' Makefile > audit.mk
for n in 32 64 128; do
  for check in 0 1; do
    [[ "$check" == 0 || "$n" == 32 ]] || continue
    for mode in baseline dedup; do
      name="tiled_matmul_${n}x${n}.opt.acc_dialect"
      job="/out/gemmini/${n}_${mode}_check${check}"
      mkdir -p "$job"
      [[ ! -f "$job/DONE" ]] || continue
      rc=0
      bash -euo pipefail -c '
        set -x
        name="$1"; job="$2"; n="$3"; mode="$4"; check="$5"; kit="$6"
        rm -f "$name".{x,o,mlir,ll,ll.mlir}
        mlir-opt-17 --mlir-print-op-generic --pass-pipeline="builtin.module(test-transform-dialect-interpreter{bind-first-extra-to-ops=linalg.quantized_matmul},test-transform-dialect-erase-schedule,linalg-generalize-named-ops)" "tiled_matmul_${n}x${n}.transform.mlir" | sed -E "s/iterator_types =/library_call=\"gemmini\", iterator_types =/g" > "$job/frontend.mlir"
        common="insert-accfg-op{accelerator=gemmini},convert-linalg-to-accfg,mlir-opt{executable=mlir-opt-17 generic=true arguments=-cse,-canonicalize,-allow-unregistered-dialect,-mlir-print-op-generic,-split-input-file}"
        "$kit/snax/compiler/snax-opt" -p "$common" "$job/frontend.mlir" -o "$job/common.mlir"
        pass=convert-accfg-to-csr
        [[ "$mode" == baseline ]] || pass="accfg-dedup,$pass"
        "$kit/snax/compiler/snax-opt" -p "$pass" "$job/common.mlir" -o "$name.mlir"
        cp "$name.mlir" "$job/lowered.mlir"
        make -j1 -f audit.mk "$name.x" "CHECK=$check"
        cp "$name.x" "$job/test.x"
        llvm-objdump-17 -d "$job/test.x" > "$job/disassembly.txt"
        sha256sum "$job/test.x" > "$job/elf.sha256"
      ' _ "$name" "$job" "$n" "$mode" "$check" "$kit" > "$job/build.log" 2>&1 || rc=$?
      printf '%s\n' "$rc" > "$job/build.exit"
      if [[ "$rc" == 0 ]]; then
        python3 /audit/scripts/spike_window.py "$job" > "$job/run.log" 2>&1 || rc=$?
        if [[ -f "$job/spike.json" ]]; then touch "$job/DONE"; fi
      fi
      printf '%s %s check%s status %s\n' "$n" "$mode" "$check" "$rc"
    done
  done
done
