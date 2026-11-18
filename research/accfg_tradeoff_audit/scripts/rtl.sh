#!/usr/bin/env bash
set -euo pipefail
ulimit -c 0
job="$1"
kind="$2"
mkdir -p "$job/$kind"
cd "$job/$kind"
exec > commands.log 2>&1
set -x
sim=/opt/snax-streamer-gemm-rtl/bin/snitch_cluster.vlt
rc=0
if [[ "$kind" == wave ]]; then
  mkfifo sim.vcd filter.pipe
  python3 /audit/scripts/filter_wave.py < filter.pipe > vcd.csv 2>filter.log &
  reader=$!
  (tee filter.pipe < sim.vcd | gzip -1n > full.vcd.gz) &
  compressor=$!
  timeout 100s "$sim" "$job/pilot.x" --vcd > stdout.txt 2>&1 || rc=$?
  if [[ "$rc" != 0 ]]; then kill "$compressor" "$reader" 2>/dev/null || true; fi
  compression_rc=0
  wait "$compressor" || compression_rc=$?
  decoder_rc=0
  wait "$reader" || decoder_rc=$?
  printf '%s\n' "$compression_rc" > compress.exit
  printf '%s\n' "$decoder_rc" > filter.exit
  rm sim.vcd filter.pipe
else
  timeout 90s "$sim" "$job/pilot.x" > stdout.txt 2>&1 || rc=$?
fi
printf '%s\n' "$rc" > sim.exit
test "$rc" = 0
if [[ "$kind" == wave ]]; then test "$decoder_rc" = 0 && test "$compression_rc" = 0; fi
for hart in 00000 00001; do
  trace="trace_hart_$hart"
  spike-dasm < "logs/$trace.dasm" | /opt/gen_trace.py --permissive -d "$trace.json" | gzip -n > "$trace.gz"
done
touch DONE
