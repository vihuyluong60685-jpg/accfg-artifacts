#!/usr/bin/env bash
set -euo pipefail
compiler="$(mktemp -d)"
tar -xf - -C "$compiler"
export PYTHONPATH="$compiler" PYTHONDONTWRITEBYTECODE=1
p1=/p1/research/p1_criticalpath_pilot/local/partial/S_k16_t3_d1_s11_r1/input.mlir
out=/out/legality
mkdir -p "$out"
{
  set -x
  python3 /v2/scripts/legality_probe.py "$p1"
  python3 /v2/scripts/legality_probe.py "$p1" --audited-call pilot_late_b
  for name in c0_s_k8_t1_b0_s11 c1_s_k8_t1_b0_s11 c2_s_k16_t1_b0_s11 c3_s_k16_t1_b0_s11; do
    ir="/out/chain/$name/input.mlir"
    python3 /v2/scripts/legality_probe.py "$ir"
    if [[ "$name" == c0* || "$name" == c2* ]]; then
      python3 /v2/scripts/legality_probe.py "$ir" --audited-call materialize
    fi
  done
} > "$out/decisions.jsonl" 2> "$out/commands.log"
for scenario in 2 3; do
  rc=0
  python3 /v2/scripts/emit_chain.py /v2/cases/tensor_chain.mlir.in "$out/refused.mlir" "$out/refused.h" 16 11 "$scenario" g     > "$out/refusal_$scenario.log" 2>&1 || rc=$?
  printf '%s\n' "$rc" > "$out/refusal_$scenario.exit"
  test "$rc" != 0
done
