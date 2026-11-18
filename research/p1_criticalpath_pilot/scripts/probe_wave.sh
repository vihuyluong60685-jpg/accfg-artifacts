#!/usr/bin/env bash
# Replay the existing ELF with its own VCD switch. A FIFO keeps disk usage bounded.
set -euo pipefail
run_id="$1"
family="${2:-partial}"
job="/out/wave_$run_id"
mkdir -p "$job"
cd "$job"
ulimit -c 0
test ! -e sim.vcd
mkfifo sim.vcd
python3 /pilot/scripts/filter_waveform.py < sim.vcd > transitions.csv 2>filter.stderr &
decoder=$!
rc=0
timeout 180s /opt/snax-streamer-gemm-rtl/bin/snitch_cluster.vlt "/out/$family/$run_id/pilot.x" --vcd > simulation.txt 2>&1 || rc=$?
if [[ "$rc" -ne 0 ]]; then kill "$decoder" 2>/dev/null || true; fi
reader_rc=0
wait "$decoder" || reader_rc=$?
printf '%s\n' "$rc" > simulator.exit
printf '%s\n' "$reader_rc" > filter.exit
rm sim.vcd
test "$rc" -eq 0
test "$reader_rc" -eq 0
