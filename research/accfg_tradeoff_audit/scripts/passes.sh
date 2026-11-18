#!/usr/bin/env bash
set -euo pipefail
kit="$(mktemp -d)"
git -c safe.directory='*' -C /accepted/snax-mlir archive 0df8b515768232036bceb6af7a6d5935b5e1a3db | tar -xf - -C "$kit"
export PYTHONPATH="$kit"
cd "$kit/kernels/streamer_matmul"
for n in 16 128 512; do
 for mode in A B C D; do
    job="/out/compile/no_copy_${n}x${n}x${n}_${mode}_r1"
    case "$mode" in
        A) flag=NO_ACCFG_OPT=1;; B) flag=DEDUP_ONLY=1;; C) flag=OVERLAP_ONLY=1;; D) flag=ACCFG_BOTH=1;;
    esac
    test -e "$job/generated.transform.mlir"
    rm -f generated.*mlir
    cp "$job/generated.transform.mlir" generated.transform.mlir
    if [[ ! -e "$job/prepare_first.exit" ]]; then
       cp "$job/prepare.exit" "$job/prepare_first.exit"
       cp "$job/pass_prepare.log" "$job/pass_prepare_first.log"
    fi
    rc=0
    (
       set -ex
       make -j1 generated.preprocfinal.mlir generated.stream.snax-opt.mlir "$flag" NO_CHECK=1
       cp generated.{preprocfinal,stream.snax-opt}.mlir "$job/"
       python3 /audit/scripts/pass_driver.py "$job" "$flag" NO_CHECK=1
    ) > "$job/pass_prepare.log" 2>&1 || rc=$?
    printf '%s\n' "$rc" > "$job/prepare.exit"
    printf '%s %s timed pass preparation %s\n' "$n" "$mode" "$rc"
 done
done
