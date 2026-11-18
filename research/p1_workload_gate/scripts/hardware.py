"""Relate RTL capture and busy signals to the validated trace timeline."""
import argparse
from bisect import bisect_right
from collections import defaultdict
import csv
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"p1_criticalpath_pilot/scripts"))
from analyze_wave import raw_signals
from validate import csv_save

SIGNALS={"stage_A","stage_B","stage_C","hart1_dma_busy","gemm_busy","gemm_config_valid",
         "streamer_csr_valid","streamer_csr_ready","streamer_busy_o"}


def state(signal,t):
    index=bisect_right(signal,(t,2**64))-1
    assert index>=0
    return signal[index][1]


def inspect(local,data):
    selected=defaultdict(list)
    with (data/"execution_phases.csv").open() as f:
        for row in csv.DictReader(f):
            if row["Mode"]=="wave":
                selected[row["Graph"],row["Method"]].append(row)
    exports,windows=[],[]
    for (graph,method),rows in sorted(selected.items()):
        signals=defaultdict(list)
        for t,event,v in raw_signals(local/graph/method/"wave/transitions.csv"):
            name=event["Signal"]
            if name in SIGNALS:
                signals[name].append((t,v))
        for r in rows:
            first,stream,wait=(int(r[k]) for k in ("First_GEMM","First_Streamer","Await1"))
            second=int(r["Next_GEMM"])
            def rising(signal,after,before):
                return next(t for t,v in signals[signal] if v and after<=t<=before)
            busy_start=rising("gemm_busy",first-1,first+4)
            busy_end=next(t for t,v in signals["gemm_busy"] if not v and t>busy_start)
            streamer_accept=next(t for t,v in signals["streamer_busy_o"] if v and stream<=t<=stream+4)
            gemm_valid=rising("gemm_config_valid",first-1,first+3)
            assert state(signals["streamer_csr_valid"],streamer_accept-1)
            assert state(signals["streamer_csr_ready"],streamer_accept-1)
            assert not any(state(signals["hart1_dma_busy"],t) for t in (first,wait,second))
            row=dict(Graph=graph,Method=method,Seed=int(r["Seed"]),First_Streamer_Capture=streamer_accept,
                     First_GEMM_Config_Valid=gemm_valid,First_Busy_Start=busy_start,First_Busy_End=busy_end,
                     GEMM_Busy_Window=busy_end-busy_start,First_Await=wait,
                     Host_Begin=int(r["Host_Begin"]),Host_End=int(r["Host_End"]),Next_GEMM=second)
            for field in "ABC":
                target,near=int(r["Next_"+field],16),int(r["Write_"+field])
                when=next(t for t,v in signals["stage_"+field] if near-1<=t<=near+4 and v==target)
                assert when>streamer_accept
                row["Stage_"+field]=when
                row["Stage_"+field+"_Inside_GEMM_Busy"]=busy_start<=when<busy_end
            for signal,items in signals.items():
                for t,v in items:
                    if first-8<=t<=max(wait,busy_end)+8:
                        exports.append(dict(Graph=graph,Method=method,Seed=int(r["Seed"]),Cycle=t,
                                            Offset=t-first,Signal=signal,Value=hex(v)))
            windows.append(row)
    assert len(windows)==8
    csv_save(data/"hardware_windows.csv",windows)
    csv_save(data/"hardware_events.csv",exports)
    print("Confirmed capture and pending-field changes for",len(windows),"waveform invocations")


if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("local",type=Path)
    ap.add_argument("data",type=Path)
    args=ap.parse_args()
    inspect(args.local,args.data)
