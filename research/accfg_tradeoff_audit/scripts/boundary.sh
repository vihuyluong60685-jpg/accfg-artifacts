#!/usr/bin/env bash
set -euo pipefail
kit="$(mktemp -d)"
git -c safe.directory='*' -C /accepted/snax-mlir archive 0df8b515768232036bceb6af7a6d5935b5e1a3db | tar -xf - -C "$kit"
export PYTHONPATH="$kit"
cd "$kit/kernels/streamer_matmul"
variant="${1:-boundary}"
cp /audit/cases/live_state.c .
fixture=/audit/cases/live_state.mlir
if [[ "$variant" == boundary_consumer ]]; then fixture=/audit/cases/live_consumer.mlir; fi
cat > live.mk <<'MAKE'
include ../../runtime/snax-streamer-gemm.rules
include ../../runtime/Makefile.rules
CFLAGS += -ffreestanding -fno-builtin -DAUDIT_LIVE_CONSUMER=$(LIVECONSUMER)
live.x: live.o live_state.o
	$(LD) $(LDFLAGS) $^ -o $@
MAKE
modes=(A B C D)
if [[ "$variant" == boundary_guarded ]]; then
  fixture=/audit/cases/live_guarded.mlir
  modes=(R)
fi
for m in "${modes[@]}"; do
  [[ "$variant" != static ]] || break
  job="/out/$variant/$m"
  mkdir -p "$job"
  rc=0
  (
    set -ex
    phases='insert-accfg-op{accelerator=snax_gemm}'
    case "$m" in B|D) phases+=,accfg-dedup;; esac
    case "$m" in C|D) phases+=,accfg-config-overlap;; esac
    "$kit/compiler/snax-opt" -p "$phases" "$fixture" -o "$job/scheduled.mlir"
    "$kit/compiler/snax-opt" -p convert-accfg-to-csr "$job/scheduled.mlir" -o live.snax-opt.mlir
    cp live.snax-opt.mlir "$job/lowered.mlir"
    rm -f live.{o,x,postproc.mlir,ll.mlir,ll,ll12} live_state.o
    consumer=0
    [[ "$variant" == boundary ]] || consumer=1
    make -j1 -f live.mk live.x "LIVECONSUMER=$consumer"
    cp live.x "$job/pilot.x"
    llvm-objdump-17 -d --disassemble-symbols=audit_loop "$job/pilot.x" > "$job/disassembly.txt"
    cd "$job"
    set +e
    timeout 60s /opt/snax-streamer-gemm-rtl/bin/snitch_cluster.vlt pilot.x > stdout.txt 2>&1
    result=$?
    set -e
    printf '%s\n' "$result" > sim.exit
    exit "$result"
  ) > "$job/commands.log" 2>&1 || rc=$?
  printf '%s\n' "$rc" > run.exit
  printf '%s boundary exit %s\n' "$m" "$rc"
done
[[ "$variant" == boundary || "$variant" == static ]] || exit 0
checks="/out/boundary/static"
mkdir -p "$checks"
cd "$kit"
for test in accfg-config-overlap accfg-insert-resets acc-dedup rocc-dedup accfg-trace-states; do
   path="$kit/tests/filecheck/transforms/$test.mlir"
   if [[ ! -f "$path" ]]; then continue; fi
   status=0
   set -x
   PATH="$kit/compiler:$PATH" timeout 25s bash -c '
     set -eo pipefail
     while IFS= read -r line; do
       line="${line#*RUN: }"
       line="${line//%s/$1}"
       line="${line//FileCheck/FileCheck-17}"
       bash -euo pipefail -c "$line"
     done < <(awk "/^\/\/ RUN: /" "$1")
   ' _ "$path" > "$checks/$test.log" 2>&1 || status=$?
   set +x
   printf '%s\n' "$status" > "$checks/$test.exit"
done
