#!/usr/bin/env bash
set -euo pipefail
ulimit -c 0
job="$1"
mode="${2:-trace}"
mkdir -p "$job/$mode"
cd "$job/$mode"
if test -e DONE; then exit 0; fi
exec > commands.log 2>&1
set -x
simulator=/opt/snax-streamer-gemm-rtl/bin/snitch_cluster.vlt
rc=0
if [[ "$mode" = wave ]]; then
  test ! -e sim.vcd
  mkfifo sim.vcd
  python3 /research/p1_criticalpath_pilot/scripts/filter_waveform.py < sim.vcd > transitions.csv 2>filter.stderr &
  reader=$!
  timeout 110s "$simulator" "$job/gate.x" --vcd > simulation.txt 2>&1 || rc=$?
  if [[ "$rc" != 0 ]]; then kill "$reader" 2>/dev/null || true; fi
  filter_rc=0
  wait "$reader" || filter_rc=$?
  printf '%s\n' "$filter_rc" > filter.exit
  rm sim.vcd
else
  timeout 60s "$simulator" "$job/gate.x" > simulation.txt 2>&1 || rc=$?
fi
printf '%s\n' "$rc" > sim.exit
test "$rc" = 0
if [[ "$mode" = wave ]]; then test "$filter_rc" = 0; fi
for hart in 00000 00001; do
  name="trace_hart_$hart"
  spike-dasm < "logs/$name.dasm" | /opt/gen_trace.py --permissive -d "$name.trace.json" | gzip -n > "$name.trace.txt.gz"
done
touch DONE
