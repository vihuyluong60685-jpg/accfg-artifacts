"""Sample DMA and GEMM occupancy in scoped newly re-run B/D cases."""
import argparse
from bisect import bisect_right
from collections import defaultdict
import csv
import re
from pathlib import Path

from collect import read_json, trace_window,write


def wave(path):
    anchors={}
    selected=[]
    with path.open() as f:
        for r in csv.DictReader(f):
            tick,signal,v=int(r["VCD_Tick"]),r["Signal"],int(r["Value"],2)
            if signal=="hart0_mcycle":
                anchors[tick]=v
            else:
                selected.append((tick,signal,v))
    ticks=sorted(anchors)
    assert sum(b-a==2 for a,b in zip(ticks[100:],ticks[101:]))>len(ticks)*.99
    times=defaultdict(list)
    for tick,signal,v in selected:
        i=bisect_right(ticks,tick)-1
        if i>=0:
            t=ticks[i]
            times[signal].append((anchors[t]+(tick-t)/2,v))
    return times


def busy(rows,a,b):
    return sum(max(0,min(y,b)-max(x,a)) for (x,v),(y,_) in zip(rows,rows[1:]) if v)


def parse(local,data):
    overview=[]
    events=[]
    gaps=[]
    for mode in "BD":
        d=local/"envelope"/f"checked_16x16x16_{mode}_r1"
        for name in ("trace","wave"):
            j=read_json(d/name/"trace_hart_00000.json")
            assert j[2]["cycles"]>0
            assert (d/name/"sim.exit").read_text().strip()=="0"
        second=read_json(d/"wave/trace_hart_00000.json")[2]
        assert second==read_json(d/"trace/trace_hart_00000.json")[2]
        pat=r"AUDIT_OUTER start=(\d+) end=(\d+) cycles=(\d+)"
        marks=[tuple(map(int,re.search(pat,(d/x/"stdout.txt").read_text()).groups())) for x in ("trace","wave")]
        assert marks[0]==marks[1]
        start,end=second["start"],second["end"]+1
        scope_end=marks[0][1]
        sig=wave(d/"wave/vcd.csv")
        for name in ("gemm_busy","hart1_dma_busy","streamer_busy_o","cluster_barrier_out","stage_A","stage_B","stage_C"):
            for t,v in sig.get(name,[]):
                if start<=t<end:
                    events.append(dict(Mode=mode,Cycle=t,Offset=t-start,Signal=name,Value=hex(v),Source="RTL VCD"))
        hart0=list(trace_window(d/"trace/trace_hart_00000.gz",start,end-1))
        hart1=list(trace_window(d/"trace/trace_hart_00001.gz",marks[0][0],scope_end))
        for op in hart1:
            if op[2].startswith("dmcpy"):
                events.append(dict(Mode=mode,Cycle=op[0],Offset=op[0]-start,Signal="hart1_dma_submit",Value=op[3],
                                   Source="hart1 retire trace"))
        near=[(op[0],nex[0]) for op,nex in zip(hart0,hart0[1:]) if op[5]==0x7c2 and nex[0]-op[0]>=100]
        for x,y in near:
            n=busy(sig["hart1_dma_busy"],x,y)
            gaps.append(dict(Mode=mode,Start=x,End=y,Offset=x-start,Cycles=y-x,DMA_Busy=n,DMA_Nonbusy=y-x-n))
        counts=len([op for op in hart1 if start<=op[0]<end and op[2].startswith("dmcpy")])
        b=sum(row["DMA_Busy"] for row in gaps if row["Mode"]==mode)
        inside=sum(y-x for x,y in near)
        overview.append(dict(Mode=mode,Inner_Cycles=end-start,Outer_Cycles=marks[0][2],Window_Source="instrumented same ELF",
              DMA_Submits_Inner=counts,Long_Barrier_Gaps=len(near),Long_Gaps_Cycles=inside,
              DMA_Busy_Inside_Gaps=b,DMA_Nonbusy_Inside_Gaps=inside-b,Outside_Gaps=end-start-inside,
              DMA_Busy_Inner=busy(sig["hart1_dma_busy"],start,end),
              GEMM_Busy_Inner=busy(sig["gemm_busy"],start,end),Wave_Equals_Trace="yes"))
    write(data/"dma_summary.csv",overview)
    write(data/"dma_windows.csv",gaps)
    write(data/"dma_events.csv",sorted(events,key=lambda e:(e["Mode"],e["Cycle"])))
    print(overview)


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for name in ("local","data"):
        p.add_argument(name,type=Path)
    args=p.parse_args()
    parse(args.local,args.data)
