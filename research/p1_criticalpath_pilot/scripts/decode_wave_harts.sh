#!/usr/bin/env bash
# Run inside the pinned image, after the wave experiments.
set -euo pipefail
for id in checked_16_D checked_16_E checked_16_F G_k16_t1_d1_s3_r1; do
  dir="/out/wave_$id"
  test "$(cat "$dir/simulator.exit")" = 0
  for hart in 00000 00001; do
    spike-dasm < "$dir/logs/trace_hart_$hart.dasm" | \
      /opt/gen_trace.py --permissive -d "$dir/trace_hart_$hart.trace.json" | \
      gzip -n > "$dir/trace_hart_$hart.trace.txt.gz"
  done
done
