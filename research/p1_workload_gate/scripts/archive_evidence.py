"""Archive actual files, hash analytical evidence, and retain numeric statuses."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import tarfile

from validate import csv_save


def digest(stream):
    h=sha256()
    for block in iter(lambda:stream.read(1024**2),b""):
        h.update(block)
    return h.hexdigest()


def file_hash(path):
    with path.open("rb") as f:
        return digest(f)


def inventory(base,paths):
    rows=[]
    for p in sorted(set(paths)):
        rows.append(dict(Path=str(p.relative_to(base)),Bytes=p.stat().st_size,SHA256=file_hash(p)))
    return rows


def statuses(local):
    record=[]
    for p in sorted(local.rglob("*.exit")):
        tag=p.relative_to(local)
        if p.name=="download.exit" and p.parent.name!="native_ad01_first":
            continue  # The identical original fetch record is copied between probes.
        rc=int(p.read_text().strip())
        log_name={"build.exit":"build.log","filter.exit":"filter.stderr","download.exit":"download.log",
                  "scheduling.exit":"scheduling.log"}.get(p.name,"commands.log")
        log=p.with_name(log_name)
        if p.name=="filter.exit" and not log.is_file():
            log=p.with_name("commands.log")
        assert log.is_file(),log
        record.append(dict(Step=str(tag),Exit=rc,Command_Log=str(log.relative_to(local)),
                           Disposition="completed" if rc==0 else "retained failure"))
    return record


def make_archive(local,raw,report):
    vault=local/"archives"
    vault.mkdir(exist_ok=True)
    archive=vault/"workload-gate.tar.gz"
    if not archive.is_file():
        subprocess.run(["tar","--use-compress-program=gzip -1","--exclude=./archives",
                        "-C",local,"-cf",archive.resolve(),"."],check=True)
    expected={r["Path"]:(r["Bytes"],r["SHA256"]) for r in raw}
    actual={}
    with tarfile.open(archive,"r:gz") as f:
        for member in f:
            if member.isfile():
                actual[member.name.removeprefix("./")]=(member.size,digest(f.extractfile(member)))
    assert actual==expected
    metadata=dict(path=str(archive.resolve()),bytes=archive.stat().st_size,sha256=file_hash(archive),
                  verified_members=len(actual),storage="separate compressed copy on the same local filesystem")
    (report/"manifests/archive.json").write_text(json.dumps(metadata,indent=2)+"\n")


def main(stage,report):
    local=stage/"local"
    indexed=statuses(local)
    raw=inventory(local,[p for p in local.rglob("*") if p.is_file() and "archives" not in p.relative_to(local).parts])
    csv_save(report/"manifests/run_status.csv",indexed)
    csv_save(report/"manifests/local_files_sha256.csv",raw)
    for base, paths, output in (
        (stage,[p for folder in ("configs","scripts","cases") for p in (stage/folder).rglob("*") if p.is_file()], "source_sha256.csv"),
        (report,[p for folder in ("logs","data","figures") for p in (report/folder).rglob("*") if p.is_file()]+list(report.glob("0*.md")), "report_sha256.csv"),
    ):
        csv_save(report/"manifests"/output,inventory(base,paths))
    make_archive(local,raw,report)
    print("Raw evidence files:",len(raw),"| bytes:",sum(r["Bytes"] for r in raw))
    print("Recorded process exits:",dict(Counter(r["Exit"] for r in indexed)))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for key in ("stage","report"):
        p.add_argument(key,type=Path)
    args=p.parse_args()
    main(args.stage,args.report)
