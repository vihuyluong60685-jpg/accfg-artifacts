# P1 critical-path pilot

Run from the research worktree root. The accepted checkout is a read-only
source for the pinned compiler object, historical diagnostics and original
results. Set ACCFG_ACCEPTED_REPO to override its path. The accepted checkout's
SNAX submodule must be at the recorded SHA, and the historical untracked
diagnostics used by E/F must be present. The experiment uses the pinned
official image and its existing simulator, with one build job and 3 GiB RAM.

```bash
stage=research/p1_criticalpath_pilot
report=reports/p1_criticalpath_pilot
accepted=${ACCFG_ACCEPTED_REPO:-/home/yanmo/research/projects/accfg-artifacts}
export ACCFG_ACCEPTED_REPO="$accepted"
bash "$stage/scripts/in_image.sh" run_original.sh
bash "$stage/scripts/in_image.sh" verify_policy_ir.sh
mapfile -t specs < "$stage/configs/partial_specs.txt"
bash "$stage/scripts/in_image.sh" run_partial.sh "${specs[@]}"
bash "$stage/scripts/in_image.sh" run_original.sh wave_controls
for variant in D E F; do
  bash "$stage/scripts/in_image.sh" probe_wave.sh "checked_16_$variant" wave_controls
done
bash "$stage/scripts/in_image.sh" probe_wave.sh G_k16_t1_d1_s3_r1
bash "$stage/scripts/in_image.sh" decode_wave_harts.sh
```

A DONE marker records a fully decoded run, not a guarantee of numerical
correctness. The validation scripts below check numerical, dynamic ordering
and comparative evidence. Repeats reuse identical ELF files. Probe runs with
K=64 use a Python-precomputed golden checker, including all matched controls.
Retried attempts and the bounded initial waveform probe are recorded in the
original retained archive. They need not be reproduced to regenerate the
successful measurements.

The host analysis used Python 3.10.12, pandas 2.2.2 and Matplotlib 3.10.9 in an
isolated virtual environment. Use that environment for these commands.

```bash
python "$stage/scripts/compare_square.py" "$accepted" "$stage/local" "$report"
python "$stage/scripts/timeline.py" "$accepted" "$report"
python "$stage/scripts/analyze_wave.py" "$stage/local" "$report"
python "$stage/scripts/verify_partial.py" "$stage/local" "$report"
python "$stage/scripts/evaluate_model.py" "$stage/local" "$report"
python "$stage/scripts/plot_results.py" "$report"
```

Raw logs and retained ELF/trace data live under local/. See the report's
manifests directory for the local archive location and SHA-256, the file
inventory and individual exit codes. The archive audit reproduces the index
of the retained original pilot session, including failure evidence and the
original research backup, using the recorded local paths.

```bash
python "$stage/scripts/archive_audit.py" "$accepted" "$stage" "$report"
```

[Chinese final report](../../reports/p1_criticalpath_pilot/08_final_comparison_report.md)
