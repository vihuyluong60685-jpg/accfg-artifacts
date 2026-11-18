"""Validate fixed inputs and index, archive, and verify the local experiment evidence."""
import argparse
import ast
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile


def digest(stream):
    sha = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        sha.update(chunk)
    return sha.hexdigest()


def sha256(path):
    with path.open("rb") as stream:
        return digest(stream)


def write_csv(path, header, rows):
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def historical(frozen, accepted, output):
    checks = {}

    def add(group, root, rel, expected=None):
        path = root / rel
        actual = sha256(path)
        if expected is not None and actual != expected:
            raise ValueError(f"Historical checksum mismatch in {path}")
        checks[group, rel] = (path.stat().st_size, actual, expected or "N/A")

    for name, expected in frozen["original_files_sha256"].items():
        add("accepted", accepted, name, expected)
    for row in read_csv(accepted / "reports/tables/opengemm_trace_audit.csv"):
        binary = Path(row["binary"])
        add("accepted", accepted, str(binary), row["binary_sha256"])
        for trace in ("trace_hart_00000.trace.txt", "trace_hart_00000.trace.json"):
            add("accepted", accepted, str(binary.with_name(trace)))
    for row in read_csv(accepted / "reports/tables/gemmini_opcode_audit.csv"):
        binary = ast.literal_eval(row["command"])[-1].removeprefix("/repo/")
        add("accepted", accepted, binary, row["binary_sha256"])
    for label, root, report, manifest, name in [
        ("prior_p1_pilot", "accfg-p1-pilot", "p1_criticalpath_pilot",
         "report_evidence_sha256.csv", "data/new_square_replays.csv"),
        ("prior_p1_gate", "accfg-p1-workload-gate", "p1_workload_gate",
         "report_sha256.csv", "data/execution_phases.csv"),
        ("prior_p1_gate", "accfg-p1-workload-gate", "p1_workload_gate",
         "report_sha256.csv", "data/correctness.json"),
        ("prior_p1_gate", "accfg-p1-workload-gate", "p1_workload_gate",
         "report_sha256.csv", "data/performance.csv"),
    ]:
        directory = accepted.parent / root / "reports" / report
        reference = {r["Path"]: r["SHA256"] for r in read_csv(directory / "manifests" / manifest)}
        add(label, directory, name, reference[name])
    write_csv(output / "historical_inputs_sha256.csv",
              ("Root", "Path", "Bytes", "SHA256", "Previously_Recorded_SHA256"),
              ((group, name, *values) for (group, name), values in sorted(checks.items())))


def run_status(local, files, output):
    specific = {
        "prepare.exit": ("pass_prepare.log",),
        "prepare_first.exit": ("pass_prepare_first.log",),
        "profile.exit": ("commands.log", "backend.log", "link.log"),
        "sim.exit": ("commands.log", "stdout.txt"),
        "filter.exit": ("commands.log", "filter.log"),
        "compress.exit": ("commands.log",),
        "run.exit": ("commands.log", "run.log", "stdout.txt"),
        "spike.exit": ("build.log", "run.log", "spike.json"),
        "objdump.exit": ("commands.log",),
    }
    rows = []
    for key in files:
        if not key.endswith(".exit"):
            continue
        record = local / key
        names = specific.get(record.name, (record.with_suffix(".log").name,))
        evidence = [str((record.parent / name).relative_to(local)) for name in names
                    if (record.parent / name).is_file()]
        rows.append((key, int(record.read_text()), " | ".join(evidence) or "N/A"))
    write_csv(output / "run_status.csv", ("Local_Exit_Record", "Exit_Code", "Local_Evidence"), rows)
    return Counter(status for _, status, _ in rows)


def archive(local, entries):
    destination = local / "archives" / "accfg-tradeoff-audit.tar.gz"
    destination.parent.mkdir(exist_ok=True)
    if not destination.exists():
        with destination.open("xb") as file:
            with tarfile.open(fileobj=file, mode="w:gz", compresslevel=1) as tar:
                for rel in entries:
                    tar.add(local / rel, arcname=rel, recursive=False)
    missing = set(entries)
    with tarfile.open(destination, "r|gz") as tar:
        for member in tar:
            if member.name not in missing or not member.isfile():
                raise ValueError(f"Unexpected archive member {member.name}")
            expected_size, expected_sha = entries[member.name]
            with tar.extractfile(member) as stream:
                if member.size != expected_size or digest(stream) != expected_sha:
                    raise ValueError(f"Archive member checksum mismatch in {member.name}")
            missing.remove(member.name)
    if missing:
        raise ValueError(f"Archive is missing {len(missing)} files")
    return destination


def main(a):
    root = Path(__file__).resolve().parents[1]
    frozen = json.loads((root / "configs/frozen.json").read_text())
    if sha256(root / "configs/matrix.json") != frozen["study_matrix_sha256"]:
        raise ValueError("Study matrix differs from frozen digest")
    head = subprocess.check_output(["git", "-C", str(a.accepted), "rev-parse", "HEAD"], text=True).strip()
    if head != frozen["base_commit"]:
        raise ValueError("Accepted reproduction checkout differs from the frozen commit")
    for pin in frozen["submodules"]:
        actual = subprocess.check_output(["git", "-C", str(a.accepted / pin["path"]),
                                          "rev-parse", "HEAD"], text=True).strip()
        if actual != pin["target"]:
            raise ValueError(f"Unexpected submodule SHA at {pin['path']}")
    historical(frozen, a.accepted, a.manifests)
    entries = {}
    for path in sorted(a.local.rglob("*")):
        relative = path.relative_to(a.local)
        if relative.parts[0] != "archives" and path.is_file():
            entries[relative.as_posix()] = (path.stat().st_size, sha256(path))
    write_csv(a.manifests / "local_files_sha256.csv", ("Local_Path", "Bytes", "SHA256"),
              ((path, *facts) for path, facts in entries.items()))
    exits = run_status(a.local, entries, a.manifests)
    bundle = archive(a.local, entries)
    record = {
        "archive_local_path": str(bundle.resolve()),
        "archive_bytes": bundle.stat().st_size,
        "archive_sha256": sha256(bundle),
        "raw_file_count": len(entries),
        "raw_bytes": sum(size for size, _ in entries.values()),
        "verified_archive_members": len(entries),
        "exit_records_by_code": dict(sorted(exits.items())),
        "study_input_sha256": frozen["study_matrix_sha256"],
        "official_base_git_sha": head,
        "archive_entry_scope": "All files under local/ except archives/. Historical originals remain in their original checkout.",
    }
    (a.manifests / "archive.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("accepted", "local", "manifests"):
        parser.add_argument(key, type=Path)
    main(parser.parse_args())
