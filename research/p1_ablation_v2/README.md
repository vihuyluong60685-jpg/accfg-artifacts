# P1 v2 ablation worktree

Run from the v2 worktree. Both old worktrees are mounted read-only. Leave the
first-stage raw analysis under its original P1 checkout or point P1_CHECKOUT
at a checkout of the frozen commit with the verified local artifacts restored.
The accepted repo supplies the pinned compiler tree as a Git archive.

```bash
stage=research/p1_ablation_v2
report=reports/p1_ablation_v2
p1=${P1_CHECKOUT:-/home/yanmo/research/projects/accfg-p1-pilot}
accepted=${ACCFG_ACCEPTED_REPO:-/home/yanmo/research/projects/accfg-artifacts}
compiler=0df8b515768232036bceb6af7a6d5935b5e1a3db
export P1_CHECKOUT="$p1" ACCFG_ACCEPTED_REPO="$accepted"
bash "$stage/scripts/in_image.sh" p1_controls.sh
bash "$stage/scripts/in_image.sh" p1_edges.sh
git -C "$accepted/snax-mlir" archive "$compiler" | bash "$stage/scripts/in_image.sh" chain_matrix.sh
git -C "$accepted/snax-mlir" archive "$compiler" | bash "$stage/scripts/in_image.sh" run_legality.sh
```

For analysis use a Python 3.10 environment with pandas 2.2.2 and Matplotlib
3.10.9. The report's data, figures, logs and manifest subdirectories are tracked.
Check simulator exit status as well as simulator markers, and rerun only records
without a DONE marker. Recorded refusal status is expected for two unsafe
early schedules. Full compile/run command logs and raw files referenced by
the manifest remain local. The archive manifest audits the retained experiment
tree, including first-attempt records from this session.

```bash
export PYTHONDONTWRITEBYTECODE=1
python "$stage/scripts/verify_runs.py" "$stage/local" "$p1" "$report"
python "$stage/scripts/compare_results.py" "$report" "$p1"
python "$stage/scripts/wave_analysis.py" "$stage/local" "$report"
python "$stage/scripts/plots.py" "$report"
python "$stage/scripts/archive_manifest.py" "$stage" "$report"
```

[Final report](../../reports/p1_ablation_v2/08_final_reviewer_assessment.md)
