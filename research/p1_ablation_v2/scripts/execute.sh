#!/usr/bin/env bash
# Run inside the frozen official container. Inputs and reference tree are read-only.
set -euo pipefail
ulimit -c 0
job="$1"
mode="${2:-trace}"
mkdir -p "$job/$mode"
cd "$job/$mode"
if [[ -e DONE ]]; then exit 0; fi
exec > commands.log 2>&1
set -x
sim=/opt/snax-streamer-gemm-rtl/bin/snitch_cluster.vlt
if [[ "$mode" == wave ]]; then
  test ! -e sim.vcd
  mkfifo sim.vcd
  python3 /p1/research/p1_criticalpath_pilot/scripts/filter_waveform.py < sim.vcd > transitions.csv 2>filter.stderr &
  reader=$!
  rc=0
  timeout 140s "$sim" "$job/pilot.x" --vcd > simulation.txt 2>&1 || rc=$?
  if [[ "$rc" != 0 ]]; then kill "$reader" 2>/dev/null || true; fi
  filter_rc=0
  wait "$reader" || filter_rc=$?
  printf '%s\n' "$filter_rc" > filter_exit
  rm sim.vcd
else
  rc=0
  timeout 70s "$sim" "$job/pilot.x" > simulation.txt 2>&1 || rc=$?
fi
printf '%s\n' "$rc" > sim_exit
test "$rc" -eq 0
if [[ "$mode" == wave ]]; then test "$filter_rc" -eq 0; fi
for hart in 00000 00001; do
  target="trace_hart_$hart"
  spike-dasm < "logs/$target.dasm" | /opt/gen_trace.py --permissive -d "$target.trace.json" | gzip -n > "$target.trace.txt.gz"
done
touch DONE
