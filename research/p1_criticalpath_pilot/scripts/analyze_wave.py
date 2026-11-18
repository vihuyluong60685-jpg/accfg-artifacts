"""Check VCD equivalence and align a small set of hardware events with mcycle."""
import argparse
from bisect import bisect_right
from collections import defaultdict
import csv
from pathlib import Path
import re

from compare_square import save
from traces import section


def logged_cycles(path):
    match = re.search(r"^P1_RESULT cycles=(\d+) start=(\d+) end=(\d+) errors=0 live_errors=0", path.read_text(), re.M)
    return tuple(map(int, match.groups()))


def raw_signals(path):
    clocks = {}
    signals = []
    with path.open() as stream:
        for row in csv.DictReader(stream):
            tick = int(row["VCD_Tick"])
            value = int(row["Value"], 2)
            if row["Signal"] == "hart0_mcycle":
                clocks[tick] = value
            else:
                signals.append((tick, row, value))
    indexes = sorted(clocks)
    # On this binary the stable mcycle updates once every two simulator ticks.
    assert sum(b-a == 2 for a,b in zip(indexes[100:], indexes[101:])) > len(indexes)*0.99

    def aligned(tick):
        anchor = indexes[bisect_right(indexes, tick)-1]
        return clocks[anchor] + (tick-anchor)/2

    return [(aligned(tick), row, value) for tick,row,value in signals if tick>=indexes[0]]


def read_wave(local, report):
    observations = []
    summary = []
    fields = []
    stages = list(csv.DictReader((report/"data/barrier_gap_breakdown.csv").open()))
    for method, case in (("D","original"), ("E","guard"), ("F","omit"), ("G","partial")):
        run = f"checked_16_{method}" if method != "G" else "G_k16_t1_d1_s3_r1"
        wave = local/f"wave_{run}"
        assert (wave/"simulator.exit").read_text().strip() == (wave/"filter.exit").read_text().strip() == "0"
        base = (local/"wave_controls"/run) if method != "G" else (local/"partial"/run)
        part = section(base/"trace_hart_00000.trace.json")
        observed = section(wave/"trace_hart_00000.trace.json")
        assert part == observed, (method, part, observed)
        if method != "G":
            first_plain = section(local/"original"/run/"trace_hart_00000.trace.json")
            assert first_plain == part
        if method == "G":
            cycles, start, stop = logged_cycles(base/"simulation.txt")
            assert (cycles, start, stop) == logged_cycles(wave/"simulation.txt")
        else:
            cycles, start, stop = part["cycles"], part["start"], part["end"]+1
        by_name = defaultdict(list)
        for t, row, value in raw_signals(wave/"transitions.csv"):
            signal = row["Signal"]
            by_name[signal].append((t,value))
            if start <= t <= stop:
                observations.append(dict(Run_ID=run, Method=method, VCD_Tick=row["VCD_Tick"],
                                         Cycle=t, Relative_Cycle=t-start, Signal=signal,
                                         Value=hex(value), Hierarchy=row["Hierarchy"], Evidence_Level="MEASURED"))
        if method == "G":
            busy = [(t,v) for t,v in by_name["gemm_busy"] if start<=t<=stop]
            first_rise, first_fall = busy[:2]
            assert first_rise[1] == 1 and first_fall[1] == 0
            a = next((t,v) for t,v in by_name["stage_A"] if first_rise[0]<t<first_fall[0])
            c = next((t,v) for t,v in by_name["stage_C"] if first_rise[0]<t<first_fall[0])
            dma = [(t,v) for t,v in by_name["hart1_dma_busy"] if start<=t<=stop]
            b = next((t,v) for t,v in by_name["stage_B"] if dma[-1][0]<t<=stop)
            fields.append(dict(Run_ID=run, Waveform_Cycles=cycles, First_GEMM_Busy_Start=first_rise[0],
                               First_GEMM_Busy_End=first_fall[0], A_Set=a[0], C_Set=c[0],
                               DMA_Busy_Start=dma[0][0], DMA_Busy_End=dma[-1][0], B_Set=b[0],
                               A_Address=hex(a[1]), B_Address=hex(b[1]), C_Address=hex(c[1])))
            continue
        active = [(a,b) for (a,v),(b,_) in zip(by_name["hart1_dma_busy"],by_name["hart1_dma_busy"][1:]) if v]
        for st in (r for r in stages if r["Variant"]==case):
            left = start + int(st["Start_Offset"])
            right = start + int(st["End_Offset"])
            busy = sum(max(0,min(b,right)-max(a,left)) for a,b in active)
            summary.append(dict(Method=method, Variant=case, Gap=int(st["Gap_Index"]),
                                Gap_Start=left, Gap_End=right,
                                Gap_Cycles=right-left, DMA_Busy_Cycles=busy,
                                Non_DMA_Busy_In_Gap=right-left-busy, Total_Window_Cycles=cycles,
                                Wave_On_Equals_Off="yes"))
    save(report/"data/wave_hardware_events.csv", observations)
    save(report/"data/wave_dma_breakdown.csv", summary)
    save(report/"data/wave_partial_proof.csv", fields)
    print("Verified unchanged timing with VCD enabled; observed staging while GEMM busy.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("local", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    read_wave(args.local,args.report)
