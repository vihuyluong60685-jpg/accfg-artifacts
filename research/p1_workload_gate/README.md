# Workload gate for P1

Run from the standalone workload-gate worktree. The original compiler checkout
and V2 worktree are mounted read-only. The V2 worktree needs the three historical
IR fixtures under its local store for calibration. All writable runs and
binary data land in this worktree's local/ directory.

```bash
stage=research/p1_workload_gate
report=reports/p1_workload_gate
accepted=${ACCFG_ACCEPTED_REPO:-/home/yanmo/research/projects/accfg-artifacts}
export ACCFG_ACCEPTED_REPO="$accepted"
compiler=0df8b515768232036bceb6af7a6d5935b5e1a3db
run() { git -C "$accepted/snax-mlir" archive "$compiler" | bash "$stage/scripts/in_image.sh" "$@"; }
run matrix.sh smoke
# Validate all smoke stdout golden/live-out markers before expanding the matrix.
for graph in mobile attention; do
  for method in A C; do
    d="$stage/local/$graph/$method/trace"
    test "$(cat "$d/sim.exit")" = 0
    test "$(rg -c '^GATE .*errors=0 live_errors=0' "$d/simulation.txt")" = 2
  done
done
run matrix.sh matrix
run matrix.sh waves
run run_opportunities.sh
```

The fixed native artifact source and SHA-256 are in frozen.json. Save the verified
download as local/native_ad01/ad01_int8.tflite and the same file as
local/native_ad01_batch1/ad01_int8.tflite. The probe preserves recognized GEMMs
separately from final pinned template scheduling.

```bash
for variant in native_ad01 native_ad01_batch1; do
  result=0
  run native_probe.sh "$variant" > "$stage/local/$variant/commands.log" 2>&1 || result=$?
  printf '%s\n' "$result" > "$stage/local/$variant/probe.exit"
done
run native_schedule.sh
```

Analyze with Python 3.10, pandas 2.2.2 and Matplotlib 3.10.9.

```bash
export PYTHONDONTWRITEBYTECODE=1
python "$stage/scripts/validate.py" "$stage/local" "$report/data"
python "$stage/scripts/summarize.py" "$stage/local" "$report/data"
python "$stage/scripts/hardware.py" "$stage/local" "$report/data"
python "$stage/scripts/figures.py" "$report"
python "$stage/scripts/archive_evidence.py" "$stage" "$report"
```

The original raw files and their separate compressed copy are local. The
published manifest preserves both the run paths and hashes. The retained
first attempts are part of this experiment session's local archive.

[Chinese final report](../../reports/p1_workload_gate/07_go_no_go_assessment.md)
