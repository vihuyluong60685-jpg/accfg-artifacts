"""Align selected VCD signals to Snitch mcycle and measured launch windows."""
import argparse
from bisect import bisect_left
from collections import defaultdict
import csv
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"p1_criticalpath_pilot/scripts"))
from analyze_wave import raw_signals
from verify_runs import markers, write_csv


def load(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def wave_summary(local,report):
    baseline = {
        (r["Family"],r["Run_ID"]):r for r in load(report/"data/performance.csv") if r["Mode"]=="trace"}
    events = defaultdict(list)
    for r in load(report/"data/timeline.csv"):
        if r["Mode"]=="wave":
            events[(r["Family"],r["Run_ID"])].append(r)
    transitions, phases=[],[]
    for row in load(report/"data/performance.csv"):
        if row["Mode"]!="wave":
            continue
        family,key=row["Family"],row["Run_ID"]
        job=local/family/key
        assert (job/"wave/filter_exit").read_text().strip()=="0"
        assert markers(job/"trace")==markers(job/"wave"), job
        meta,_=markers(job/"wave")
        for k in ("Cycles","Host_Instructions","CSR_Writes","Branches","ELF_SHA256"):
            assert row[k]==baseline[(family,key)][k]
        raw = defaultdict(list)
        for t,event,value in raw_signals(job/"wave/transitions.csv"):
            signal=event["Signal"]
            raw[signal].append((t,value))
            if meta["start"]<=t<=meta["end"] and signal!="hart0_mcycle":
                transitions.append(dict(Family=family,Run_ID=key,Cycle=t,Relative_Cycle=t-meta["start"],
                                        Signal=signal,Value=hex(value),Hierarchy=event["Hierarchy"]))
        for event in events[(family,key)]:
            start,end=int(event["First_GEMM"]),int(event["Second_GEMM"])
            phase=dict(Family=family,Run_ID=key,Slot=event["Slot"],Start=start,End=end)
            for name in ("gemm_busy","hart1_dma_busy","streamer_busy_o"):
                samples=raw[name]
                active=sum(max(0,min(end,b)-max(start,a)) for (a,v),(b,_) in zip(samples,samples[1:]) if v)
                phase[name+"_cycles"]=active
            first_gemm = next(t for t,v in raw["gemm_busy"] if v and t>=start)
            first_idle = next(t for t,v in raw["gemm_busy"] if not v and t>first_gemm)
            phase.update(First_GEMM_Busy=first_gemm, First_GEMM_Idle=first_idle)
            for key_name in "ABC":
                cpu=int(event[f"{key_name}_Write"])
                arr=raw["stage_"+key_name]
                nearest=bisect_left(arr,(cpu-1,0))
                matches=[(t,v) for t,v in arr[nearest:nearest+5]
                         if abs(t-cpu)<=4 and v==int(event["Next_"+key_name],16)]
                assert matches, (job,key_name,cpu)
                stage=min(matches,key=lambda item:abs(item[0]-cpu))[0]
                phase[key_name+"_stage"]=stage
                phase[key_name+"_inside_first_GEMM"]=first_gemm<=stage<first_idle
            phases.append(phase)
    assert phases
    write_csv(report/"data/vcd_events.csv",transitions)
    write_csv(report/"data/vcd_phase_summary.csv",phases)
    print(f"Verified same cycles and matched recorded staging transitions for {len(phases)} wave launch pairs")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("local",type=Path)
    parser.add_argument("report",type=Path)
    args=parser.parse_args()
    wave_summary(args.local,args.report)
