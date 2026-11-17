#!/usr/bin/env python3
"""Supplementary native trace counts; never replaces the official result file."""
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def measure(case):
    size, option = case
    if option == "C baseline":
        binary = ROOT / f"gemmini-rocc-tests/build/bareMetalC/tiled_matmul_ws_{size}x{size}-baremetal"
    else:
        binary = ROOT / f"gemmini-rocc-tests/bareMetalMLIR/tiled_matmul_{size}x{size}.opt.acc_dialect.x"
    command = ["spike", "-l", "--extension=gemmini", str(binary)]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    counter = subprocess.Popen([str(ROOT / "reports/raw/spike_opcode_audit")],
                               stdin=process.stdout, stdout=subprocess.PIPE)
    process.stdout.close()
    output, _ = counter.communicate()
    spike_exit = process.wait()
    if spike_exit != 0 or counter.returncode != 0:
        raise RuntimeError(f"Supplementary audit failed: {command}, {spike_exit}, {counter.returncode}")
    data = json.loads(output)
    data.update({"size": size, "option": option, "spike_exit_code": spike_exit,
                 "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                 "command": command, "scope": "whole-program trace, including startup; first printed cycle-counter interval recorded separately"})
    print(json.dumps(data), flush=True)
    return data


def main():
    cases = [(n, option) for n in [32, 64, 128, 256, 512]
             for option in ["C baseline", "MLIR deduplicated"]]
    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(measure, cases))
    (ROOT / "reports/tables/gemmini_opcode_audit.json").write_text(json.dumps(rows, indent=2) + "\n")
    with (ROOT / "reports/tables/gemmini_opcode_audit.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
