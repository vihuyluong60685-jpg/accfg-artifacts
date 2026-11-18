"""Inventory retained v2 data and recorded process exits."""
import argparse
from hashlib import sha256
from pathlib import Path

from verify_runs import write_csv

LOGS = {"trace":"commands.log","wave":"commands.log","build":"build.log"}


def digest(path):
    h=sha256()
    with path.open("rb") as stream:
        for data in iter(lambda:stream.read(1024**2),b""):
            h.update(data)
    return h.hexdigest()


def inventory(roots,base):
    files=[]
    for root in roots:
        files.extend((r for r in root.rglob("*") if r.is_file()) if root.is_dir() else (root,))
    return [dict(Path=path.relative_to(base),Bytes=path.stat().st_size,SHA256=digest(path)) for path in sorted(set(files))]


def status_for(local):
    results=[]
    for folder in ("p1_controls","p1_edges","chain","chain_initial_build"):
        for job in sorted((local/folder).iterdir()):
            if (job/"build_exit").exists():
                results.append(entry(local,job.name,"build",job/"build_exit",
                                     job/LOGS["build"],folder))
            for mode in ("trace","wave"):
                if (job/mode/"sim_exit").is_file():
                    results.append(entry(local,job.name,"simulator_"+mode,
                                         job/mode/"sim_exit",job/mode/LOGS[mode],folder))
                if (job/mode/"filter_exit").is_file():
                    results.append(entry(local,job.name,"wave_filter",
                                         job/mode/"filter_exit",job/mode/"filter.stderr",folder))
    for code in sorted((local/"legality").glob("refusal_*.exit")):
        results.append(entry(local,code.stem,"reject_unsafe",code,code.with_suffix(".log"),"legality"))
    if (local/"legality_initial/probe.exit").is_file():
        initial=local/"legality_initial"
        results.append(entry(local,"first-analysis","xdsl_legality_probe",initial/"probe.exit",
                             initial/"commands.log","legality_initial"))
    return results


def entry(local,job,process,code,log,family):
    result=int(code.read_text().strip())
    return dict(Family=family,Run_ID=job,Process=process,Exit=result,
                Status="expected refusal" if process=="reject_unsafe" and result!=0 else ("completed" if result==0 else "failed"),
                Local_Command_Log=log.relative_to(local),Exit_Record=code.relative_to(local))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    for k in ("stage","report"):
        parser.add_argument(k,type=Path)
    opts=parser.parse_args()
    local=opts.stage/"local"
    statuses=status_for(local)
    write_csv(opts.report/"manifests/run_status.csv",statuses)
    raw=inventory([local],local)
    write_csv(opts.report/"manifests/local_artifacts_sha256.csv",raw)
    evidence_roots=[opts.report/k for k in ("data","figures","logs")]
    evidence=inventory(evidence_roots+list(opts.report.glob("0*.md")),opts.report)
    write_csv(opts.report/"manifests/report_sha256.csv",evidence)
    source=inventory([opts.stage/k for k in ("scripts","cases","configs")],opts.stage)
    write_csv(opts.report/"manifests/sources_sha256.csv",source)
    print(f"Hashed {len(raw)} retained files / {sum(row['Bytes'] for row in raw)} B, {len(evidence)} evidence files, {len(source)} input files and indexed {len(statuses)} exits")
