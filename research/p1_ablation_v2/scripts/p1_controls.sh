#!/usr/bin/env bash
set -euo pipefail
original=/p1/research/p1_criticalpath_pilot/local/partial
out=/out/p1_controls
mkdir -p "$out"
for k in 16 32 64; do
  for d in 0 1; do
    methods=(s g g-late s-reg s-compact)
    if [[ "$k" == 16 ]]; then methods+=(g-private g-full-late); fi
    for method in "${methods[@]}"; do
      name="${method}_k${k}_t3_d${d}_s11"
      job="$out/$name"
      mkdir -p "$job"
      base="${method:0:1}"
      src="$original/${base^^}_k${k}_t3_d${d}_s11_r1"
      if [[ ! -f "$job/pilot.x" ]]; then
        printf '%s\n' "$src" > "$job/source_path"
        (cd "$src"; test "$(sha256sum pilot.x | cut -d' ' -f1)" = "$(cut -d' ' -f1 elf.sha256)")
        if [[ "$method" == s || "$method" == g ]]; then
          cp "$src/pilot.x" "$job/pilot.x"
        else
          python3 /v2/scripts/rewrite_elf.py "$method" "$src/pilot.x" "$src/disassembly.txt" "$job/pilot.x" "$job/patch.json"
        fi
        sha256sum "$job/pilot.x" > "$job/elf.sha256"
        llvm-objdump-17 -d "$job/pilot.x" > "$job/disassembly.txt"
      fi
      status=0
      bash /v2/scripts/execute.sh "$job" || status=$?
      printf '%s trace exit %s\n' "$name" "$status"
      if [[ "$k" == 16 && "$d" == 1 && "$status" == 0 ]]; then
        bash /v2/scripts/execute.sh "$job" wave || status=$?
        printf '%s wave exit %s\n' "$name" "$status"
      fi
    done
  done
done
