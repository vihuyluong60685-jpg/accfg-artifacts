#!/usr/bin/env python3
"""Independently validate new measurements; README values are references only."""
import hashlib
import json
import math
from pathlib import Path
import re
import shutil

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
LABELS = {"NO_ACCFG_OPT": "Base (MLIR)", "DEDUP_ONLY": "Deduplicated",
          "OVERLAP_ONLY": "Overlapped", "ACCFG_BOTH": "With Optimizations"}


def geomean(values):
    return math.exp(sum(math.log(float(x)) for x in values) / len(values))


def references():
    opengemm, gemmini = {}, {}
    metrics = ["csrw", "csrwi", "cycles", "ops", "cycles_peak", "no_opt_cycles",
               "speedup", "setup ins", "Ioc", "p_attain_seq", "p_attain_conc", "p_attain_opt", "p_meas"]
    for line in (ROOT / "README.md").read_text().splitlines():
        m = re.match(r"^\s*\d+\s+(\d+)\s+(Base \(MLIR\)|Deduplicated|Overlapped|With Optimizations)\s+(.*)$", line)
        if m:
            values = list(map(float, m[3].split()))
            if len(values) == len(metrics):
                opengemm[(int(m[1]), m[2])] = dict(zip(metrics, values))
        m = re.match(r"^\s*\d+\s+(C baseline|MLIR deduplicated)\s+(\d+)\s+(.*)$", line)
        if m:
            values = list(map(float, m[3].split()))
            fields = ["rocc", "cycles", "ops", "bw_conf_eff", "Ioc", "p_attain_seq"]
            if len(values) == len(fields):
                gemmini[(int(m[2]), m[1])] = dict(zip(fields, values))
    assert len(opengemm) == 24 and len(gemmini) == 10, "Incomplete README reference tables"
    return opengemm, gemmini


def main():
    tables = ROOT / "reports/tables"
    tables.mkdir(exist_ok=True)
    rows, summary = [], {"reference_source": "README.md at paper-original; PDF Figure 10–12 and Appendix A.6"}
    op_ref, gm_ref = references()
    for experiment, file, reference in [("OpenGeMM", "opengemm_results.pkl", op_ref),
                                         ("Gemmini", "gemmini_results.pkl", gm_ref)]:
        path = ROOT / "artifacts" / file
        if not path.exists():
            summary[experiment] = {"status": "NOT TESTED", "reason": "No fresh result file"}
            for (size, option), metrics in reference.items():
                for metric, value in metrics.items():
                    rows.append(dict(Experiment=experiment, Matrix_Size=size, Optimization=option,
                                     Metric=metric, Paper_Value=value, Reproduced_Value=None,
                                     Absolute_Error=None, Relative_Error=None, Status="NOT TESTED"))
            continue
        frame = pd.read_pickle(path)
        assert not frame.duplicated(["size", "option"]).any()
        if experiment == "OpenGeMM":
            assert set(frame["size"]) == {16, 32, 64, 128, 256, 512} and len(frame) == 24
            assert set(map(str, frame["option"])) == set(LABELS)
            assert all(frame["cycles"] > 0)
            independent = []
            trace_audit = []
            for _, r in frame.iterrows():
                n = int(r["size"])
                base = frame[(frame["size"] == n) & (frame["option"] == "NO_ACCFG_OPT")].iloc[0]
                ops = 2 * n ** 3
                ioc = ops / (r["csrwi"] * 5 / 8 + 4 * r["csrw"])
                calculated = {"ops": ops, "speedup": float(base["cycles"] / r["cycles"]),
                              "Ioc": float(ioc), "p_meas": float(ops / r["cycles"]),
                              "p_attain_seq": float(1 / (1 / 1024 + 1 / (2 * ioc))),
                              "p_attain_conc": float(min(1024, 2 * ioc))}
                for metric, value in calculated.items():
                    assert math.isclose(float(r[metric]), value, rel_tol=1e-12), metric
                independent.append({"size": n, "option": str(r["option"]), **calculated})
                folder = ROOT / "snax-mlir/kernels/streamer_matmul/results" / f"tiled_matmul_generated_{n}x{n}x{n}" / f"test_generated_{n}x{n}x{n}_{r['option']}"
                trace = folder / "trace_hart_00000.trace.txt"
                lines, instructions = 0, 0
                with trace.open() as stream:
                    for line in stream:
                        lines += 1
                        if re.match(r"^\s*\d+\s+\d+\s+M\s+0x[0-9a-fA-F]+\s+", line):
                            instructions += 1
                binary = folder / "generated.stream.x"
                trace_audit.append({"size": n, "option": str(r["option"]),
                                    "hart0_trace_lines": lines, "hart0_instruction_lines": instructions,
                                    "scope": "whole hart0 trace, including startup; not tiling-loop instruction count",
                                    "binary": str(binary.relative_to(ROOT)),
                                    "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()})
            pd.DataFrame(trace_audit).to_csv(tables / "opengemm_trace_audit.csv", index=False)
            ratios = [x["speedup"] for x in independent if x["option"] == "ACCFG_BOTH"]
            summary[experiment] = {"status": "PASS", "rows": len(frame), "geomean_speedup": geomean(ratios),
                                   "maximum_speedup": max(ratios), "independent_results": independent,
                                   "measurement": "Verilator simulated tiling-loop cycles; not hardware measurement"}
            for metric, expected, actual in [("geomean_speedup_x", 1.99, geomean(ratios)),
                                              ("maximum_speedup_x", 2.71, max(ratios))]:
                error = abs(actual - expected)
                rows.append(dict(Experiment=experiment, Matrix_Size="ALL", Optimization="ACCFG_BOTH / NO_ACCFG_OPT",
                                 Metric=metric, Paper_Value=expected, Reproduced_Value=actual,
                                 Absolute_Error=error, Relative_Error=error / expected,
                                 Status="PASS" if error <= 0.005 else "FAIL"))
            frame["option"] = frame["option"].astype(str).map(LABELS)
        else:
            assert len(frame) == 10 and set(frame["size"]) == {32, 64, 128, 256, 512}
            assert set(frame["option"]) == {"C baseline", "MLIR deduplicated"}
            assert all(frame["cycles"] > 0) and all(frame["rocc"] > 0)
            frame["ops"] = frame["size"] ** 3 * 2
            frame["bw_conf_eff"] = 16 * frame["rocc"] / (3 * frame["cycles"])
            frame["Ioc"] = frame["ops"] / (16 * frame["rocc"])
            frame["p_attain_unrounded"] = 1 / (1 / 512 + 3 * frame["cycles"] / frame["ops"])
            frame["p_attain_seq"] = frame["p_attain_unrounded"].round().astype(int)
            pivot = frame.pivot(index="size", columns="option", values="p_attain_seq")
            ratios = list(pivot["MLIR deduplicated"] / pivot["C baseline"])
            summary[experiment] = {"status": "PASS", "rows": len(frame), "geomean_speedup": geomean(ratios),
                                   "improvement_percent": (geomean(ratios) - 1) * 100,
                                   "measurement": "Spike instruction count and modeled performance (CPI=3, peak=512); not hardware cycles"}
            actual = (geomean(ratios) - 1) * 100
            error = abs(actual - 10.5)
            rows.append(dict(Experiment=experiment, Matrix_Size="ALL", Optimization="MLIR deduplicated / C baseline",
                             Metric="geomean_improvement_percent", Paper_Value=10.5, Reproduced_Value=actual,
                             Absolute_Error=error, Relative_Error=error / 10.5,
                             Status="PASS" if error <= 0.05 else "FAIL"))
        frame.to_csv(tables / (experiment.lower() + "_measured.csv"), index=False)
        for _, r in frame.iterrows():
            key = (int(r["size"]), str(r["option"]))
            for metric, expected in reference[key].items():
                actual = float(r[metric])
                error = abs(actual - expected)
                rows.append(dict(Experiment=experiment, Matrix_Size=key[0], Optimization=key[1],
                                 Metric=metric, Paper_Value=expected, Reproduced_Value=actual,
                                 Absolute_Error=error, Relative_Error=error / abs(expected) if expected else None,
                                 Status="PASS" if error <= 0.00000051 else "FAIL"))
    pd.DataFrame(rows).to_csv(tables / "paper_alignment.csv", index=False)
    summary["alignment_pass"] = sum(r["Status"] == "PASS" for r in rows)
    summary["alignment_fail"] = sum(r["Status"] == "FAIL" for r in rows)
    summary["alignment_not_tested"] = sum(r["Status"] == "NOT TESTED" for r in rows)
    figures = ROOT / "reports/figures"
    figures.mkdir(exist_ok=True)
    summary["files"] = []
    for path in sorted((ROOT / "artifacts").iterdir()):
        if not path.is_file() or path.name == ".empty":
            continue
        if path.suffix == ".png":
            shutil.copy2(path, figures / path.name)
        summary["files"].append({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                                 "mtime_ns": path.stat().st_mtime_ns,
                                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (tables / "result_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
