"""Score matched experimental interventions and check against the frozen P1."""
import argparse
from collections import defaultdict
import csv
import json
from math import exp, log
from pathlib import Path

from verify_runs import write_csv


def load(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def same_counts(a,b):
    assert all(a[k]==b[k] for k in ("Host_Instructions","Branches","Calls","CSR_Writes",
                                   "Returns","Launches","Await_Sequences","Loads","Stores","Moves","Nops","ELF_Bytes"))


def same_branch_path(a,b):
    assert a["Branch_Path_SHA256"] == b["Branch_Path_SHA256"]


def summarize(report,p1):
    performance=load(report/"data/performance.csv")
    baseline=load(p1/"reports/p1_criticalpath_pilot/data/partial_comparison.csv")
    old={row["Run_ID"]:row for row in baseline}
    checks=json.loads((report/"data/correctness.json").read_text())
    assert not checks["failures"]
    checks={(r["run"],r["mode"]):r for r in checks["verified"]}
    groups=defaultdict(dict)
    for row in performance:
        if row["Mode"]!="trace":
            continue
        key=tuple(row[k] for k in ("Family","Scenario","K","Trips","DMA_Bytes","Seed"))
        groups[key][row["Method"]]=row
    controls, independent, side=[],[],[]
    for (family,scenario,k,trips,bytes_,seed),group in sorted(groups.items(),key=lambda item:(item[0][0],item[0][1],*(int(v) for v in item[0][2:]))):
        base=dict(Family=family,Scenario=scenario,K=k,Trips=trips,DMA_Bytes=bytes_,Seed=seed)
        c={m:int(r["Cycles"]) for m,r in group.items()}
        if family.startswith("p1"):
            n=f"k{k}_t{trips}_d{int(int(bytes_)>0)}_s{seed}_r1"
            for method in ("s","g"):
                historical=old[method.upper()+"_"+n]
                assert all(group[method][key]==historical[key] for key in ("Cycles","CSR_Writes","Host_Instructions","ELF_SHA256"))
            same_counts(group["g"],group["g-late"])
            same_branch_path(group["g"],group["g-late"])
            assert checks[(group["g"]["Run_ID"],"trace")]["opcode_histogram"] == checks[(group["g-late"]["Run_ID"],"trace")]["opcode_histogram"]
            common=dict(**base,S=c["s"],G=c["g"],G_Late=c["g-late"],Original_Saving=c["s"]-c["g"],
                        Strict_Early_Saving=c["g-late"]-c["g"],Strict_Speedup=c["g-late"]/c["g"])
            if family=="p1_edges":
                expected=checks[(group["g"]["Run_ID"],"trace")]["meta"]["choices"]
                side.append(dict(**common,Observed_Choice_Mask=expected))
                continue
            assert int(group["s"]["Host_Instructions"])-int(group["g"]["Host_Instructions"])==18
            assert int(group["s-reg"]["Host_Instructions"])==int(group["s"]["Host_Instructions"])
            assert int(group["s-reg"]["Nops"])==18
            assert int(group["s-compact"]["Host_Instructions"])==int(group["g"]["Host_Instructions"])
            assert len({group[m]["Branches"] for m in group})==1
            row=dict(**common,S_Reg=c["s-reg"],S_Compact=c["s-compact"],S_To_Reg=c["s"]-c["s-reg"],
                     Reg_To_Compact=c["s-reg"]-c["s-compact"],S_To_Compact=c["s"]-c["s-compact"],
                     Same_Count_Serial_Minus_G=c["s-compact"]-c["g"],
                     S_To_G_Speedup=c["s"]/c["g"])
            if "g-private" in c:
                same_counts(group["g-private"],group["g-full-late"])
                row.update(G_Private=c["g-private"],G_Full_Late=c["g-full-late"],
                           Full_Early_Saving=c["g-full-late"]-c["g-private"])
            controls.append(row)
        elif "g" not in c:
            independent.append(dict(**base,Decision="retain-serial",S=c["s"],Gain_vs_Safe_Reference=0))
        else:
            same_counts(group["g"],group["l"])
            same_branch_path(group["g"],group["l"])
            assert checks[(group["g"]["Run_ID"],"trace")]["opcode_histogram"] == checks[(group["l"]["Run_ID"],"trace")]["opcode_histogram"]
            independent.append(dict(**base,Decision="whole" if scenario=="all-ready" else "partial",S=c["s"],G=c["g"],
                                    L=c["l"],W=c.get("w","N/A"),Strict_Early_Saving=c["l"]-c["g"],
                                    Strict_Speedup=c["l"]/c["g"],Gain_vs_Safe_Reference=c["s"]-c["g"]))
    assert len(controls)==6 and len(side)==2 and len(independent)==11
    write_csv(report/"data/causal_p1.csv",controls)
    write_csv(report/"data/dynamic_b_controls.csv",side)
    write_csv(report/"data/negative_and_cross_family.csv",independent)
    print("S/G geomean",exp(sum(log(r["S_To_G_Speedup"]) for r in controls)/len(controls)))
    print("G-late/G geomean",exp(sum(log(r["Strict_Speedup"]) for r in controls)/len(controls)))
    for key in ("Original_Saving","Strict_Early_Saving","S_To_Reg","Reg_To_Compact","S_To_Compact","Same_Count_Serial_Minus_G"):
        print(key,[r[key] for r in controls])
    print("Tensor-chain",[(r["K"],r["DMA_Bytes"],r["Trips"],r.get("Strict_Early_Saving")) for r in independent if r["Scenario"]=="tensor-chain"])


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("report",type=Path)
    parser.add_argument("p1",type=Path)
    arguments=parser.parse_args()
    summarize(arguments.report,arguments.p1)
