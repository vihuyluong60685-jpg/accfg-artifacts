"""Matched oracle over executable candidates plus audit-aware opportunity counts."""
import argparse
from collections import defaultdict
import csv
import json
from math import exp, log
from pathlib import Path
import re

from validate import GRAPHS, METHODS, SEEDS, csv_save

FIXED={"A": "Base","B":"Dedup","C":"Both","M0":"D (safe late)","M3":"F (static A/B)"}
MASK_METHODS={m: ("C" if m==7 else f"M{m}") for m in range(8)}


def read(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def geometric(values):
    return exp(sum(log(value) for value in values)/len(values))


def diagnostics(local,data):
    decisions = [json.loads(r) for r in (local/"opportunities/decisions.jsonl").read_text().splitlines()]
    (data/"static_decisions.json").write_text(json.dumps(decisions,indent=2)+"\n")
    flatten = []
    sites = []
    for row in decisions:
        common=dict(Graph=row["Graph"],Category="workload" if row["Graph"] in GRAPHS else "calibration",
                    Original_Fields=row["Fields_Before_Dedup"],Effective_Fields=row["Effective_Fields"],
                    Source_IR=row["Input"],Capture=row["Stable_State_Capture_CSR"],
                    Both_Observation=row["Both_Observation"])
        for field in row["Fields"]:
            flatten.append(dict(**common,**field,Deduplicated=False,Both_Moved=field["Field"] in row["Both_Moved"]))
        for field in row["Deduplicated_Fields"]:
            flatten.append(dict(**common,Field=field,Deduplicated=True,Both_Moved=False))
        sites.append(dict(**common,Safe_Early=len(row["Safe_Early_Fields"]),
                           Late=len(row["Late_Fields"]),Strict_Partial_Opportunity=row["Strict_Partial_Opportunity"],
                           Missed_Safe_Fields=len(row["Missed_Safe_Fields"])))
    csv_save(data/"field_opportunities.csv",flatten)
    csv_save(data/"opportunity_sites.csv",sites)
    return sites


def native(local,data):
    rows=[]
    for target in ("native_ad01","native_ad01_batch1"):
        d=local/target
        out=(d/"ad01.dispatch.mlir").read_text()
        tosa=(d/"ad01.tosa.mlir").read_text()
        counts={name:len(re.findall(rf'\b{re.escape(pattern)}\b',text))
                for name,pattern,text in (("TOSA_Fully_Connected","tosa.fully_connected",tosa),
                    ("Remaining_Linalg_Generic","linalg.generic",out),("ACCFG_Launches","accfg.launch",out),
                    ("ACCFG_Setups","accfg.setup",out),("SNAX_Streaming_Regions","snax_stream.streaming_region",out))}
        reason="need to check behaviour in this case"
        assert reason in (d/"scheduling.log").read_text()
        rows.append(dict(Probe=target,**counts,
                         Recognized_SNAX_GEMM=out.count('library_call = "snax_gemm"'),
                         IR_Probe_Exit=int((d/"probe.exit").read_text()),
                         Template_Exit=int((d/"scheduling.exit").read_text()),
                         Observed_Template_Reason=reason,Performance="N/A"))
    csv_save(data/"native_support.csv",rows)
    return rows


def aggregate(local,data):
    records=read(data/"performance.csv")
    by=defaultdict(dict)
    instructions={}
    for r in records:
        if r["Mode"]=="trace":
            key=(r["Graph"],int(r["Seed"]))
            by[key][r["Method"]]=int(r["Cycles"])
            instructions[(key,r["Method"])]=(int(r["CSR_Writes"]),int(r["Host_Instructions"]))
    assert tuple(by)==tuple((graph,seed) for graph in GRAPHS for seed in SEEDS)
    assert all(set(g)==set(METHODS) for g in by.values())
    assert all(r["Correctness"]=="PASS" for r in records)
    best_static_partial={graph:min(range(1,7),key=lambda m:
                               (geometric([by[graph,s][f"M{m}"]/by[graph,s]["M0"] for s in SEEDS]),m)) for graph in GRAPHS}
    fixed_ratio=lambda method:geometric([v[method]/v["A"] for v in by.values()])
    public_fixed=min(FIXED,key=fixed_ratio)
    best_fixed=min(METHODS,key=fixed_ratio)
    pairs=[]
    marginals=[]
    grid=[]
    for (graph,seed),v in by.items():
        e=v[f"M{best_static_partial[graph]}"]
        oracle_masks=min(range(8),key=lambda m:(v[MASK_METHODS[m]],m))
        oracle=min(METHODS,key=lambda method:v[method])
        writes,cpu=instructions[((graph,seed),"C")]
        pairs.append(dict(Graph=graph,Seed=seed,A_Base=v["A"],B_Dedup=v["B"],C_Both=v["C"],
                          D_Safe=v["M0"],E_Partial=e,E_Mask=best_static_partial[graph],F_Static=v["M3"],
                          All_Oracle=oracle,All_Oracle_Cycles=v[oracle],Layout_Oracle_Mask=oracle_masks,
                          Layout_Oracle_Cycles=v[MASK_METHODS[oracle_masks]],Strict_Saving=v["M0"]-v[MASK_METHODS[oracle_masks]],
                          Strict_Saving_Pct=100*(v["M0"]-v[MASK_METHODS[oracle_masks]])/v["M0"],
                          Public_Best_Fixed=public_fixed,Best_Fixed=best_fixed,Best_Fixed_Cycles=v[best_fixed],
                          Best_Fixed_Regret=(v[best_fixed]-v[oracle])/v[oracle],
                          CSR_Percentage_Host_Instructions=100*writes/cpu))
        for mask, method in MASK_METHODS.items():
            grid.append(dict(Graph=graph,Seed=seed,Mask=mask,Method=method,Cycles=v[method],
                             Early_Fields="".join(field for bit,field in enumerate("ABC") if mask & (1<<bit)),
                             Saving_vs_Safe=v["M0"]-v[method],Saving_vs_Whole=v["C"]-v[method]))
            for bit,field in enumerate("ABC"):
                if not mask & (1<<bit):
                    enlarged=mask | (1<<bit)
                    marginals.append(dict(Graph=graph,Seed=seed,Field=field,Other_Mask=mask,
                                      New_Mask=enlarged,Saving=v[method]-v[MASK_METHODS[enlarged]]))
    csv_save(data/"schedule_oracle.csv",pairs)
    csv_save(data/"layout_grid.csv",grid)
    csv_save(data/"field_marginals.csv",marginals)
    strategies=[]
    for name in (*METHODS,"E_best_subset_by_graph","oracle"):
        cell=[]
        for case in pairs:
            group=by[case["Graph"],case["Seed"]]
            cycles=case["All_Oracle_Cycles"] if name=="oracle" else case["E_Partial"] if name.startswith("E_") else group[name]
            cell.append((cycles,case["All_Oracle_Cycles"],case["A_Base"]))
        strategies.append(dict(Policy=name,Matches_Oracle=sum(a==b for a,b,_ in cell),
                               Geomean_Speedup_vs_Base=geometric([c/a for a,_,c in cell]),
                               Mean_Regret=sum((a-b)/b for a,b,_ in cell)/len(cell),
                               Worst_Regret=max((a-b)/b for a,b,_ in cell)))
    csv_save(data/"policies.csv",strategies)
    sites=diagnostics(local,data)
    native_rows=native(local,data)
    included=[s for s in sites if s["Category"]=="workload"]
    stats=dict(Static_Workload_Transitions=len(included),
               Opportunities_Any_Safe=sum(s["Safe_Early"]>0 for s in included),
               Opportunities_Strict_Partial=sum(s["Strict_Partial_Opportunity"] for s in included),
               Safe_Pointer_Fields=sum(s["Safe_Early"] for s in included),
               Fields_Missed_By_Both=sum(s["Missed_Safe_Fields"] for s in included),
               Dynamic_Workload_Invocations=len(pairs),Exposed_Single_Field_Cases=sum(r["Other_Mask"]==0 and r["Saving"]>0 for r in marginals),
               Eligible_Dynamic_Field_Cases=sum(r["Other_Mask"]==0 for r in marginals),Strongest_Fixed=best_fixed,
               Overall_Oracle_Geomean_Speedup_Over_Fixed=geometric([r["Best_Fixed_Cycles"]/r["All_Oracle_Cycles"] for r in pairs]),
               Strict_Subsets_Negative_vs_D=sum(1<=r["Mask"]<=6 and r["Saving_vs_Safe"]<0 for r in grid),
               Strict_Subsets_Negative_vs_C=sum(1<=r["Mask"]<=6 and r["Saving_vs_Whole"]<0 for r in grid),
               Native_Probes=native_rows)
    (data/"summary.json").write_text(json.dumps(stats,indent=2)+"\n")
    print(json.dumps(stats))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("local",type=Path)
    p.add_argument("data",type=Path)
    args=p.parse_args()
    aggregate(args.local,args.data)
