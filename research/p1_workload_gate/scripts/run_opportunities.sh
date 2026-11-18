#!/usr/bin/env bash
set -euo pipefail
kit="$(mktemp -d)"
tar -xf - -C "$kit"
export PYTHONPATH="$kit"
out=/out/opportunities
mkdir -p "$out"
{
  set -x
  probe=/gate/scripts/opportunities.py
  for graph in mobile attention; do
    orig="/out/$graph/A/base.mlir"
    dedup="/out/$graph/B/scheduled.mlir"
    both="/out/$graph/C/scheduled.mlir"
    python3 "$probe" "$graph" "$orig" "$dedup" "$both" --audited publish_middle
    python3 "$probe" "${graph}_untrusted" "$orig" "$dedup" "$both"
  done
  prev=/v2/research/p1_ablation_v2/local/chain
  for fixture in c0_s_k8_t1_b0_s11 c2_s_k16_t1_b0_s11 c3_s_k16_t1_b0_s11; do
    serial="$prev/$fixture/input.mlir"
    if [[ "$fixture" == c0* ]]; then
      python3 "$probe" calibration_late_A "$serial" "$serial" "$prev/c0_w_k8_t1_b0_s11/scheduled.mlir" --audited materialize
    elif [[ "$fixture" == c2* ]]; then
      python3 "$probe" calibration_all_late "$serial" "$serial" "$serial" --audited materialize
    else
      python3 "$probe" calibration_state_observer "$serial" "$serial" "$serial"
    fi
  done
} > "$out/decisions.jsonl" 2> "$out/commands.log"
