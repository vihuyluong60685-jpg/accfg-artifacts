#!/usr/bin/env python3
"""Hash retained results and audit logs without loading large traces into RAM."""
import csv
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parents[2]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, help="Completed record_command.py experiment run ID")
    args = parser.parse_args()
    if Path(args.run_id).name != args.run_id:
        raise SystemExit("Use a run ID, not a filesystem path")
    run = json.loads((ROOT / "reports/logs" / args.run_id / "metadata.json").read_text())
    if run["status"] == "RUNNING":
        raise SystemExit("Experiment has not finished; retain the running-state metadata")
    started = datetime.datetime.fromisoformat(run["started_at"]).timestamp()
    targets = {}
    for directory, kind in [("artifacts", "official_result"),
                             ("reports/figures", "figure_copy"),
                             ("snax-mlir/kernels/streamer_matmul/results", "opengemm_trace_or_binary")]:
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and path.name != ".empty":
                targets[path] = kind
    for size in [32, 64, 128, 256, 512]:
        for relative in [f"gemmini-rocc-tests/build/bareMetalC/tiled_matmul_ws_{size}x{size}-baremetal",
                         f"gemmini-rocc-tests/bareMetalMLIR/tiled_matmul_{size}x{size}.opt.acc_dialect.x"]:
            path = ROOT / relative
            if path.exists():
                targets[path] = "gemmini_binary"
    commands = []
    for metadata in sorted((ROOT / "reports/logs").glob("*/metadata.json")):
        data = json.loads(metadata.read_text())
        output = metadata.with_name("output.log")
        # A running command log is not immutable and must not be given a final hash.
        if data["status"] == "RUNNING":
            continue
        targets[metadata] = "command_metadata"
        if output.exists():
            targets[output] = "command_log"
        commands.append({k: data.get(k) for k in ["run_id", "started_at", "finished_at", "exit_code", "status", "code_commit", "output_sha256"]}
                        | {"command": shlex.join(data["command"]), "metadata": str(metadata.relative_to(ROOT))})
    rows = []
    for path, kind in sorted(targets.items()):
        result = kind in {"official_result", "figure_copy", "opengemm_trace_or_binary", "gemmini_binary"}
        fresh = result and path.stat().st_mtime >= started
        rows.append({"path": str(path.relative_to(ROOT)), "kind": kind, "bytes": path.stat().st_size,
                     "mtime_ns": path.stat().st_mtime_ns, "sha256": sha256(path),
                     "generated_during_run": fresh if result else "not applicable",
                     "experiment_run_id": run["run_id"] if fresh else "preexisting or see command_audit.csv",
                     "experiment_code_commit": run["code_commit"] if fresh else "not attributed to this experiment"})
    tables = ROOT / "reports/tables"
    for name, records in [("result_file_manifest.csv", rows), ("command_audit.csv", commands)]:
        with (tables / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
    print("Hashed", len(rows), "retained files; recorded", len(commands), "completed commands")


if __name__ == "__main__":
    main()
