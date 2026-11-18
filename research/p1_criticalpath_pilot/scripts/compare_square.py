"""Read the accepted PKL and traces, then compare the new unchanged controls."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import re

import pandas as pd
from traces import counts, read_trace, section, window

COMPILER_SHA = "0df8b515768232036bceb6af7a6d5935b5e1a3db"

METHODS = dict(A="NO_ACCFG_OPT", B="DEDUP_ONLY", C="OVERLAP_ONLY", D="ACCFG_BOTH")
LABELS = dict(A="Base", B="Dedup", C="Overlap", D="Both", E="Guard", F="Omit", G="Partial")
OLD = {
    "no_copy": {16: [169, 84, 225, 91, 84, 77], 32: [608, 251, 671, 224], 64: [2624, 1136, 2352, 968]},
    "checked": {16: [1802, 1700, 1778, 1664, 1694, 1680], 32: [11985, 11758, 11882, 11545], 64: [85195, 83424, 84294, 83460]},
}


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def rows_from_log(path):
    records = {}
    for line in path.read_text().splitlines():
        if line.startswith("CASE "):
            key = tuple(line.split()[1:])
            records[key] = {}
        elif m := re.fullmatch(r"([0-9a-f]{64})  generated.stream.x", line):
            records[key]["sha"] = m[1]
        elif m := re.match(r"window (\d+) instruction_lines (\d+)", line):
            records[key].update(cycles=int(m[1]), instructions=int(m[2]))
        elif line.startswith("csr_mnemonics "):
            import ast
            hist = ast.literal_eval(line.removeprefix("csr_mnemonics "))
            count = sum(v for insn, v in hist.items()
                        if (m := re.search(r"unknown_([0-9a-f]+)", insn))
                        and int(m[1], 16) in set(range(0x3C0, 0x3D5)) | set(range(0x3D7, 0x3DB)))
            records[key]["writes"] = count
    return records


def save(path, rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, restval="N/A", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def compare(repo, local, report):
    prior = repo / "reports/research_opportunities/diagnostics"
    artifact = repo / "artifacts/opengemm_results.pkl"
    assert sha(artifact) == "b98df083c2d786f924c2a667a4f5812d64ca46b61c129026bc11e481c8bcb0bf"
    pkl = pd.read_pickle(artifact)
    hist = rows_from_log(prior / "rtl_checked.log")
    reference = rows_from_log(prior / "rtl_open16_reference.log")
    prior_versions = json.loads((prior / "run_context.json").read_text())["diagnostic_files_sha256"]
    for filename in ("rtl_checked.log", "rtl_open16_reference.log", "rtl_open16_repeat.log"):
        assert sha(prior / filename) == prior_versions[filename]

    checked_control = {}
    base_rows = []
    new_rows = []
    for scope, by_size in OLD.items():
        for size, expected in by_size.items():
            shape = f"{size}x{size}x{size}"
            best = min(expected)
            both = expected[3]
            for idx, method in enumerate("ABCDEFG"):
                name = f"{scope}_{size}_{method}"
                baseline = {"Matrix_Size": shape, "Scope": scope, "Method": method, "Compiler_Source_SHA": COMPILER_SHA,
                            "Label": LABELS[method], "Evidence": "HISTORICAL"}
                if idx >= len(expected):
                    baseline.update(Correctness="N/A", Cycles="N/A", Evidence="N/A")
                    base_rows.append(baseline)
                    continue

                if scope == "no_copy" and idx < 4:
                    old_dir = (repo / "snax-mlir/kernels/streamer_matmul/results"
                               / f"tiled_matmul_generated_{shape}" / f"test_generated_{shape}_{METHODS[method]}")
                    trace_file = old_dir / "trace_hart_00000.trace.txt"
                    part = section(old_dir / "trace_hart_00000.trace.json")
                    metrics = counts(window(read_trace(trace_file), part["start"], part["end"]))
                    cycles = int(pkl[(pkl["size"] == size) & (pkl["option"] == METHODS[method])].iloc[0].cycles)
                    assert part["cycles"] == cycles
                    hist_data = dict(cycles=cycles, writes=metrics["CSR_Writes"],
                                     instructions=metrics["Host_Instructions"],
                                     sha=sha(old_dir / "generated.stream.x"))
                    listed = list(csv.DictReader((repo / "reports/tables/opengemm_trace_audit.csv").open()))
                    assert any(r["binary_sha256"] == hist_data["sha"] for r in listed)
                    source = str(trace_file.relative_to(repo))
                elif idx >= 4:
                    hist_data = reference[(scope, "guard" if method == "E" else "omit")]
                    source = str((prior / "rtl_open16_reference.log").relative_to(repo))
                else:
                    hist_data = hist[(scope, str(size), METHODS[method])]
                    source = str((prior / "rtl_checked.log").relative_to(repo))

                assert hist_data["cycles"] == expected[idx], name
                if method == "D":
                    checked_control[(scope, size)] = hist_data
                base_rows.append({
                    **baseline, "Cycles": hist_data["cycles"], "CSR_Writes": hist_data["writes"],
                    "Host_Instructions": hist_data["instructions"], "ELF_SHA256": hist_data["sha"],
                    "Correctness": "golden" if scope == "checked" else "not_checked",
                    "Speedup_vs_Base": expected[0] / expected[idx], "Speedup_vs_Both": both / expected[idx],
                    "Delta_Cycles_vs_Both": expected[idx] - both,
                    "CSR_Writes_Saved_vs_Both": checked_control[(scope, size)]["writes"] - hist_data["writes"] if idx >= 3 else "",
                    "Delta_Host_Instructions_vs_Both": hist_data["instructions"] - checked_control[(scope, size)]["instructions"] if idx >= 3 else "",
                    "Regret": (expected[idx] - best) / best if scope == "checked" else "N/A",
                    "Evidence_Source": source,
                })

                new_dir = local / "original" / name
                if not (new_dir / "DONE").is_file():
                    continue
                part = section(new_dir / "trace_hart_00000.trace.json")
                fresh = counts(window(read_trace(new_dir / "trace_hart_00000.trace.txt.gz"), part["start"], part["end"]))
                rc = int((new_dir / "sim_exit").read_text())
                assert rc == 0
                assert (part["cycles"], fresh["CSR_Writes"], fresh["Host_Instructions"]) == (
                    expected[idx], hist_data["writes"], hist_data["instructions"]), name
                new_rows.append({
                    **baseline, "Evidence": "NEW", "Cycles": part["cycles"], **fresh,
                    "Correctness": "golden" if scope == "checked" else "not_checked",
                    "ELF_SHA256": (new_dir / "elf.sha256").read_text().split()[0],
                    "ELF_Bytes": int((new_dir / "elf.bytes").read_text()),
                    "Build_Ms": int((new_dir / "build_ms").read_text()), "Simulator_Exit": rc,
                    "DMA": "enabled" if scope == "checked" else "off in timed window",
                    "Same_Cycle_And_Counts_As_Historical": "yes", "Run_ID": name,
                })

            control = checked_control[(scope, size)]
            for row in base_rows:
                if row["Matrix_Size"] == shape and row["Scope"] == scope and isinstance(row["Cycles"], int):
                    row["CSR_Writes_Saved_vs_Both"] = control["writes"] - row["CSR_Writes"]
                    row["Delta_Host_Instructions_vs_Both"] = row["Host_Instructions"] - control["instructions"]

    save(report / "data/baseline_comparison.csv", base_rows)
    save(report / "data/new_square_replays.csv", new_rows)
    print(f"Verified {sum(isinstance(r['Cycles'], int) for r in base_rows)} historical and {len(new_rows)} new square rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("accepted", type=Path)
    parser.add_argument("local", type=Path)
    parser.add_argument("report", type=Path)
    arguments = parser.parse_args()
    compare(arguments.accepted, arguments.local, arguments.report)
