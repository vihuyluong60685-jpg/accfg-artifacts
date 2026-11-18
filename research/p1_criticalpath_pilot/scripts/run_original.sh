#!/usr/bin/env bash
# Inside the pinned image. stdin is an archive of the pinned SNAX compiler.
set -euo pipefail
archive="$(mktemp -d)"
cd "$archive"
tar -xf -
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$archive"
cd kernels/streamer_matmul
for scope in no_copy checked; do
  flags=()
  [[ "$scope" != no_copy ]] || flags+=(NO_CHECK=1)
  for size in 16 32 64; do
    methods=(A B C D)
    [[ "$size" != 16 ]] || methods+=(E F)
    for method in "${methods[@]}"; do
      dest="/out/original/${scope}_${size}_${method}"
      mkdir -p "$dest"
      if test -f "$dest/DONE"; then continue; fi
      rm -f generated.* data.c data.h main.o data.o
      rm -rf logs
      case "$method" in
        A) mode=NO_ACCFG_OPT=1;;
        B) mode=DEDUP_ONLY=1;;
        C) mode=OVERLAP_ONLY=1;;
        *) mode=ACCFG_BOTH=1;;
      esac
      {
        set -x
        python3 -c "from genbenchmark import generate_tiled_benchmark; generate_tiled_benchmark($size, $size, $size, [8, 8])"
        start_ns="$(date +%s%N)"
        if [[ "$method" = E || "$method" = F ]]; then
          make -s -j1 generated.preprocfinal.mlir
          pipe="$(make -n -B generated.stream.snax-opt.mlir "$mode" "${flags[@]}" | awk '/snax-opt -p/ {print}')"
          pipe="${pipe/convert-accfg-to-csr,/}"
          pipe="${pipe/-o generated.stream.snax-opt.mlir/-o original.accfg.mlir}"
          eval "$pipe"
          reference=guard
          [[ "$method" != F ]] || reference=omit
          python3 /accepted/reports/research_opportunities/diagnostics/open16_reference.py "$reference" original.accfg.mlir candidate.accfg.mlir
          ../../compiler/snax-opt -p convert-accfg-to-csr candidate.accfg.mlir -o generated.stream.snax-opt.mlir
          cp candidate.accfg.mlir "$dest/"
        fi
        make -j1 generated.stream.x "$mode" "${flags[@]}" "SIZE_M=$size" "SIZE_N=$size" "SIZE_K=$size"
        printf '%s\n' "$(( ($(date +%s%N) - start_ns) / 1000000 ))" > "$dest/build_ms"
        sha256sum generated.stream.x > "$dest/elf.sha256"
        wc -c < generated.stream.x > "$dest/elf.bytes"
        sim_rc=0
        timeout 90s /opt/snax-streamer-gemm-rtl/bin/snitch_cluster.vlt generated.stream.x || sim_rc=$?
        printf '%s\n' "$sim_rc" > "$dest/sim_exit"
        test "$sim_rc" -eq 0
        make -j1 traces
        for hart in 00000 00001; do
          name="trace_hart_$hart.trace"
          gzip -n -c "logs/$name.txt" > "$dest/$name.txt.gz"
          cp "logs/$name.json" "$dest/"
        done
        touch "$dest/DONE"
      } > "$dest/commands.log" 2>&1
      printf 'complete %s %s %s exit=%s\n' "$scope" "$size" "$method" "$sim_rc"
    done
  done
done
