#!/usr/bin/env bash
# Profile real Make rules at the lowered-IR and final-link entry points.
set -euo pipefail
kit="$(mktemp -d)"
git -c safe.directory='*' -C /accepted/snax-mlir archive 0df8b515768232036bceb6af7a6d5935b5e1a3db | tar -xf - -C "$kit"
export PYTHONPATH="$kit"
cd "$kit/kernels/streamer_matmul"
python3 gendata.py --n 16 --m 16 --k 16
make -j1 NO_CHECK=1 main.o data.o > /out/backend_common.log 2>&1
for seed in ABCD BCDA CDAB; do
  for ((i=0;i<4;i++)); do
    m="${seed:i:1}"
    dir="/out/backend/${seed}_$m"
    mkdir -p "$dir"
    rm -f generated.*
    cp "/out/compile/no_copy_16x16x16_${m}_r1/generated.stream.snax-opt.mlir" .
    python3 /audit/scripts/process_metrics.py "$dir/backend.json" make -j1 NO_CHECK=1 generated.stream.o > "$dir/backend.log" 2>&1
    python3 /audit/scripts/process_metrics.py "$dir/link.json" make -j1 NO_CHECK=1 generated.stream.x > "$dir/link.log" 2>&1
    test "$(wc -l < "$dir/link.log")" = 1
    printf '0\n' > "$dir/profile.exit"
  done
done
