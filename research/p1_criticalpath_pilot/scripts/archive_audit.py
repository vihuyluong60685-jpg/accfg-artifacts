"""Catalog retained evidence and check the accepted checkout against frozen hashes."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tarfile


def digest(stream):
    result = sha256()
    for chunk in iter(lambda: stream.read(1024*1024), b""):
        result.update(chunk)
    return result.hexdigest()


def file_hash(path):
    with path.open("rb") as stream:
        return digest(stream)


def csv_output(path, columns, rows):
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(columns)
        writer.writerows(rows)


def inventory(root):
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path.relative_to(root), path.stat().st_size, file_hash(path)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", repo, *args], text=True).strip()


def frozen_audit(frozen, accepted, report):
    lines = []
    assert git(accepted, "rev-parse", "HEAD") == frozen["base_commit"]
    assert git(accepted, "rev-parse", "origin/repro/accfg-2026") == frozen["base_commit"]
    assert git(accepted, "rev-parse", "paper-original^{}") == frozen["paper_original"]
    assert git(accepted, "rev-parse", "main") == frozen["paper_original"]
    assert git(accepted, "diff", "HEAD", "--name-only", "--ignore-submodules=none") == ""
    lines.extend(("Accepted checkout: "+frozen["base_commit"], "main and paper-original: "+frozen["paper_original"]))
    for sub in frozen["submodules"]:
        path = accepted/sub["path"]
        assert git(path, "rev-parse", "HEAD") == sub["actual"] == sub["target"]
        assert git(path, "diff", "HEAD", "--name-only", "--ignore-submodules=none") == ""
        lines.append(f"{sub['actual']}  {sub['path']}")
    for name, expected in frozen["original_files_sha256"].items():
        assert file_hash(accepted/name) == expected, name
        lines.append(f"{expected}  {name}")
    for filename in ("fig10_bar_plot.png", "fig_11_bar_plot.png", "fig_12_roofline.png"):
        assert file_hash(accepted/"reports/figures"/filename) == frozen["original_files_sha256"][f"artifacts/{filename}"]
    backup = Path(frozen["backup_local_path"])
    assert file_hash(backup) == frozen["backup_sha256"]
    with tarfile.open(backup, "r:gz") as archive:
        files = {m.name: digest(archive.extractfile(m)) for m in archive.getmembers() if m.isfile()}
    for name, expected in files.items():
        assert file_hash(accepted/name) == expected, name
    remaining = {str(path.relative_to(accepted)) for path in (accepted/"reports/research_opportunities").rglob("*") if path.is_file()}
    assert remaining == files.keys()
    lines.append(f"{frozen['backup_sha256']}  {backup} ({len(files)} regular files match checkout)")
    (report/"logs/baseline_preservation.txt").write_text("\n".join(lines)+"\n")


def run_status(local, report):
    rows = []
    for family, count in (("original",28), ("partial",44), ("wave_controls",3)):
        dirs = sorted(folder for folder in (local/family).iterdir() if (folder/"DONE").is_file())
        assert len(dirs) == count
        for folder in dirs:
            status = (folder/"sim_exit").read_text().strip()
            assert status == "0"
            target = folder.relative_to(local)
            rows.append((family, folder.name, "Verilator via timeout", status, "complete",
                         target/"commands.log", target/"sim_exit"))
    waves = ("checked_16_D","checked_16_E","checked_16_F","G_k16_t1_d1_s3_r1")
    for name in waves:
        target = Path(f"wave_{name}")
        for tool, filename in (("Verilator --vcd via timeout","simulator.exit"),
                               ("FIFO VCD decoder","filter.exit")):
            status = (local/target/filename).read_text().strip()
            assert status == "0"
            rows.append(("wave", name, tool, status, "complete",
                         target/("simulation.txt" if filename=="simulator.exit" else "filter.stderr"), target/filename))
    target = Path("waveform_probe")
    status = (local/target/"probe.exit").read_text().strip()
    assert status == "153"
    rows.append(("wave_probe", "checked_16_D", "bounded Verilator VCD probe", status,
                 "stopped by 64 MiB file limit; replaced by FIFO", target/"probe.stdout", target/"probe.exit"))
    for method in ("S","W"):
        name = f"{method}_k64_t3_d0_s11_r1"
        target = Path("attempts/k64_slow_checker")/name
        status = (local/target/"sim_exit").read_text().strip()
        assert status == "124"
        rows.append(("partial_attempt", name, "Verilator via timeout", status,
                     "timed kernel ended; on-target golden checker timed out; rerun with independent arrays",
                     target/"simulation.txt", target/"sim_exit"))
    rows.extend((
        ("partial_attempt","K64 first batch G direct","batch interrupted","N/A",
         "no numeric exit or completed run saved; replaced with fast golden","attempts/holdout_first.log","N/A"),
        ("partial_attempt","initial link","ld.lld through Clang","1",
         "undefined C interface symbol; wrapper corrected","partial_first_link_error.log","partial_first_link_error.log"),
        ("lowering_attempt","initial G policy IR","snax-opt","N/A",
         "parse error after path collision; successful replay kept; first numeric status absent",
         "attempts/verify_policy_ir_first.log","N/A"),
    ))
    csv_output(report/"manifests/run_status.csv",
               ("Family","Run_ID","Process","Exit","Disposition","Local_Log","Exit_Evidence"), rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("accepted", type=Path)
    parser.add_argument("stage", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    frozen = json.loads((args.stage/"configs/frozen_baseline.json").read_text())
    local = args.stage/"local"
    frozen_audit(frozen, args.accepted, args.report)
    run_status(local, args.report)
    kept = list(inventory(local))
    csv_output(args.report/"manifests/local_artifacts_sha256.csv", ("Path","Bytes","SHA256"), kept)
    compact = [(Path(folder)/path, size, sha)
               for folder in ("data","figures","logs") for path,size,sha in inventory(args.report/folder)]
    csv_output(args.report/"manifests/report_evidence_sha256.csv", ("Path","Bytes","SHA256"), compact)
    print(f"Cataloged {len(kept)} local files ({sum(row[1] for row in kept)} bytes) and {len(compact)} report evidence files")


if __name__ == "__main__":
    main()
