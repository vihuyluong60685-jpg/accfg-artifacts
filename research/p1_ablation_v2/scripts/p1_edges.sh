#!/usr/bin/env bash
set -euo pipefail
original=/p1/research/p1_criticalpath_pilot/local/partial
for seed in 1 11; do
  for method in s g g-late; do
    dest="/out/p1_edges/${method}_k16_t1_d1_s${seed}"
    base="${method:0:1}"
    src="$original/${base^^}_k16_t1_d1_s${seed}_r1"
    mkdir -p "$dest"
    if [[ ! -f "$dest/pilot.x" ]]; then
      (cd "$src"; test "$(sha256sum pilot.x | cut -d' ' -f1)" = "$(cut -d' ' -f1 elf.sha256)")
      printf '%s\n' "$src" > "$dest/source_path"
      if [[ "$method" == g-late ]]; then
        python3 /v2/scripts/rewrite_elf.py "$method" "$src/pilot.x" "$src/disassembly.txt" "$dest/pilot.x" "$dest/patch.json"
      else
        cp "$src/pilot.x" "$dest/pilot.x"
      fi
      llvm-objdump-17 -d "$dest/pilot.x" > "$dest/disassembly.txt"
      sha256sum "$dest/pilot.x" > "$dest/elf.sha256"
    fi
    rc=0
    bash /v2/scripts/execute.sh "$dest" || rc=$?
    printf '%s trace exit %s\n' "$dest" "$rc"
  done
done
