"""Construct comparable metric pairs, checked Pareto fronts, and descriptive summaries."""
import argparse
from collections import defaultdict
import json
from math import exp,log
from pathlib import Path
from statistics import median

from collect import read,read_json,write

PAIRS=("AB","AC","AD","BD","CD")
OPEN_UNITS={
    "Cycles":"cycle","Host_Instructions":"instruction","Config_CSR_Writes":"write",
    "Named_CSR_Writes_Paper_Definition":"instruction","CSR_Instruction_Bytes":"ISA instruction byte",
    "Outer_Cycles":"cycle","ELF_Bytes":"byte","Text_Bytes":"byte","Rodata_Bytes":"byte",
    "Data_Bytes":"byte","Bss_Bytes":"byte","Debug_Section_Bytes":"byte","Kernel_Symbol_Bytes":"byte",
    "Timed_Kernel_Symbol_Bytes":"byte","Timed_Static_Instructions":"instruction",
    "Timed_Static_Branches":"instruction","Dynamic_Branches":"instruction",
    "Dynamic_Loads":"instruction","Dynamic_Stores":"instruction","SP_LoadStore":"instruction",
    "Timed_Stack_Frame_Bytes":"byte","Timed_ABI_Save_Restore_Pairs":"register",
    "Config_After_Final_Launch":"write",
}
COMPILER="0df8b515768232036bceb6af7a6d5935b5e1a3db"
GEMMINI="4fec505cadacec4c371305b90973fa18758e9ac0"


def metric(a,b,key,unit,expected="lower",**rest):
    parse=lambda x: float(x) if isinstance(x,str) else x
    try:
        x,y=parse(a),parse(b)
    except (TypeError,ValueError):
        x,y=a,b
        delta,pct,classification="N/A","N/A","NOT MEASURED"
    else:
        delta=y-x
        pct=100*delta/x if x else "N/A"
        favorable=delta<0 if expected=="lower" else delta>0
        classification="UNCHANGED" if delta==0 else "BENEFIT" if favorable else "REGRESSION"
    return dict(**rest,Metric=key,Unit=unit,Direction=expected,Baseline_Value=x,Optimized_Value=y,
                Absolute_Difference=delta,Relative_Change_Percent=pct,Benefit_or_Regression=classification)


def group(rows,key):
    found=defaultdict(list)
    for r in rows: found[key(r)].append(r)
    return found


def pairinfo(r0,r1,platform,shape,scope):
    return dict(Workload="tiled-matmul",Platform=platform,Matrix_Size=shape,
                Mode=r1["Mode"],Baseline_Mode=r0["Mode"],Measurement_Scope=scope,
                Evidence_Type=r1["Evidence"], Run_ID=r1["Run_ID"],Baseline_Run_ID=r0["Run_ID"],
                Git_SHA=COMPILER if platform=="OpenGeMM" else f"{COMPILER}; {GEMMINI}",
                Evidence_Path=r1.get("Path","data/gemmini_cases.csv"),Correctness=r1["Correctness"])


def pivot_stats(rows, groups=("Measurement_Scope",), sample="Matrix_Size", label="Worst_Shape"):
    def by_scope_and_pair(row):
        return (*(row[key] for key in groups), row["Baseline_Mode"]+row["Mode"])

    result=[]
    for (*scope,pair),data in sorted(group(rows,by_scope_and_pair).items()):
        full=[r for r in data if r["Metric"]=="Cycles"]
        ratios=[r["Baseline_Value"]/r["Optimized_Value"] for r in full]
        slowest=min(full,key=lambda r:r["Baseline_Value"]/r["Optimized_Value"])
        result.append(dict(Scope=scope[0],**dict(zip(groups[1:],scope[1:],strict=True)),Pair=pair,Cells=len(full),Geomean_Speedup=exp(sum(map(log,ratios))/len(ratios)),
              Best_Speedup=max(ratios),Worst_Speedup=min(ratios),**{label:slowest[sample]},
              Regressions=sum(r["Relative_Change_Percent"]>0 for r in full),
              Max_Slowdown_Pct=max(0,max(r["Relative_Change_Percent"] for r in full))))
    return result


def run(data,local):
    both=[]
    fronts=[]
    open_pairs=[]
    opengemm=read(data/"opengemm_cases.csv")
    for (scope,shape),series in group(opengemm,lambda r:(r["Scope"],r["Shape"])).items():
        modes={r["Mode"]:r for r in series}
        assert set(modes)==set("ABCD")
        for x,y in PAIRS:
            a,b=modes[x],modes[y]
            for key,unit in OPEN_UNITS.items():
                xval,yval=a.get(key,"N/A"),b.get(key,"N/A")
                if xval=="N/A" or yval=="N/A":
                    continue
                notes=""
                if key=="CSR_Instruction_Bytes":
                    notes="32-bit encoding length times configuration-only dynamic count; not bus bytes"
                if key in {"ELF_Bytes","Debug_Section_Bytes"}:
                    notes="host file size, not loaded code"
                row=metric(xval,yval,key,unit,**pairinfo(a,b,"OpenGeMM",shape,scope),Notes=notes)
                open_pairs.append(row)
        checks=("Cycles","Text_Bytes","Config_CSR_Writes")
        if all(r["Correctness"]=="GOLDEN_PASS" and all(r[k]!="N/A" for k in checks) for r in series):
            for r in series:
                values=tuple(int(r[k]) for k in checks)
                dominate=[other["Mode"] for other in series if
                          (z:=tuple(int(other[k]) for k in checks))!=values and all(a<=b for a,b in zip(z,values,strict=True))]
                fronts.append(dict(Scope=scope,Shape=shape,Mode=r["Mode"],**dict(zip(checks,values,strict=True)),
                                  Pareto="DOMINATED" if dominate else "FRONTIER",
                                  Dominated_By=" ".join(dominate),Correctness=r["Correctness"]))
    both.extend(open_pairs)
    write(data/"runtime_summary.csv",pivot_stats([r for r in open_pairs if r["Metric"]=="Cycles"]))
    write(data/"pareto_comparison.csv",fronts)

    graph_pairs=[]
    graphs=read(data/"prior_graph_phases.csv")
    for (graph,seed),series in group(graphs,lambda r:(r["Graph"],r["Seed"])).items():
        modes={r["Mode"]:r for r in series}
        assert set(modes)==set("ABC")
        for x,y in ("AB","AC","BC"):
            for key,unit in (("Cycles","cycle"),("Config_CSR_Writes","write"),("Host_Instructions","instruction")):
                graph_pairs.append(metric(modes[x][key],modes[y][key],key,unit,
                    Workload=graph,Platform="OpenGeMM",Matrix_Size="N/A",Mode=y,Baseline_Mode=x,
                    Measurement_Scope="prior reduced graph marked window",Evidence_Type="PRIOR_READ_ONLY_GRAPH",
                    Evidence_Path="data/prior_graph_phases.csv",Run_ID=f"{graph}_{seed}_{y}",
                    Baseline_Run_ID=f"{graph}_{seed}_{x}",Git_SHA="6c97864e905a84a9cc80387f09cbca53b83a55f2",
                    Correctness=modes[y]["Correctness"],Notes="Prior workbench; C is Both; full graph window, no timed DMA"))
    both.extend(graph_pairs)
    graph_cycles=[dict(r,Seed=r["Run_ID"].split("_")[1]) for r in graph_pairs if r["Metric"]=="Cycles"]
    graph_summary=pivot_stats(graph_cycles,("Measurement_Scope","Workload"),"Seed","Worst_Seed")
    write(data/"prior_graph_runtime_summary.csv",graph_summary)

    gem=read(data/"gemmini_cases.csv")
    models=[]
    for (scope,n),series in group(gem,lambda r:(r["Scope"],r["Size"])).items():
        assert len(series)==2
        a,b=series
        if scope.startswith("official"):
            a,b=sorted(series,key=lambda r:r["Mode"])
            for cpi in (1,2,3,5):
                ideal=2*int(n)**3/512
                x=ideal+cpi*int(a["Counter_Interval"])
                y=ideal+cpi*int(b["Counter_Interval"])
                models.append(dict(Size=n,Assumed_CPI=cpi,Modeled_Cycles_C=x,Modeled_Cycles_MLIR=y,Speedup=x/y,
                                  Kernel_Model="paper fixed peak, sequential",Evidence="MODEL"))
        else:
            a,b=sorted(series,key=lambda r:r["Mode"])
        items=(("Counter_Interval","Spike instruction-counter tick"),("Whole_Trace_RoCC","instruction"),
               ("In_Interval_RoCC","instruction"),("RoCC_Config_Funct7_0","instruction"),
               ("Model_Attainable_Ops_Per_Cycle","modeled op/cycle"))
        for key,unit in items:
            if a.get(key,"N/A")=="N/A" or b.get(key,"N/A")=="N/A":
                continue
            row=metric(a[key],b[key],key,unit,"higher" if key.startswith("Model") else "lower",
                       **pairinfo(a,b,"Gemmini",n,scope),Notes="No silicon latency")
            if key.startswith("Model"):
                row["Evidence_Type"]="MODEL_PAPER_FORMULA"
            both.append(row)
    write(data/"gemmini_cpi_sensitivity.csv",models)

    summary=[]
    samples=group(read(data/"build_samples.csv"),lambda r:(r["Size"],r["Mode"]))
    for (n,mode),series in sorted(samples.items(),key=lambda i:(int(i[0][0]),i[0][1])):
        wall=[float(r["Elapsed_Seconds"]) for r in series]
        memory=[int(r["Max_Child_RSS_KiB"]) for r in series]
        row=dict(Size=n,Mode=mode,Repeats=len(series),Wall_Median=median(wall),Wall_Min=min(wall),Wall_Max=max(wall),
                 RSS_Median_KiB=median(memory),RSS_Min_KiB=min(memory),RSS_Max_KiB=max(memory))
        summary.append(row)
    write(data/"build_summary.csv",summary)
    for n,series in group(summary,lambda r:r["Size"]).items():
        m={r["Mode"]:r for r in series}
        for x,y in PAIRS:
            for name,unit in (("Wall_Median","second"),("RSS_Median_KiB","KiB")):
                both.append(metric(m[x][name],m[y][name],name,unit,Workload="native build process",
                      Platform="OpenGeMM",Matrix_Size=n,Mode=y,Baseline_Mode=x,Measurement_Scope="complete fresh make",
                      Evidence_Type="NEW_TIMED_BUILD",Evidence_Path="data/build_samples.csv",Run_ID=f"build_{n}_{x}{y}",
                      Git_SHA=COMPILER,Correctness="BUILD_PASS",Notes="4 rotated samples, new subprocess each"))
    stress=[read_json(f) for f in sorted((local/"stress").glob("*.json"))]
    write(data/"structure_stress.csv",stress)
    grouped=group(read(data/"pass_samples.csv"),lambda r:(r["Size"],r["Mode"],r["Stage"]))
    pass_summary=[]
    for (n,mode,stage),series in sorted(grouped.items()):
        durations=[float(r["Milliseconds"]) for r in series]
        first=series[0]
        pass_summary.append(dict(Size=n,Mode=mode,Stage=stage,Repeats=len(series),Median_MS=median(durations),
                                Min_MS=min(durations),Max_MS=max(durations),Ops_Before=first["Ops_Before"],
                                Ops_After=first["Ops_After"],IR_Bytes_Before=first["IR_Bytes_Before"],
                                IR_Bytes_After=first["IR_Bytes_After"]))
    write(data/"pass_summary.csv",pass_summary)
    wave={r["Mode"]:r for r in read(data/"dma_summary.csv")}
    for k,u in (("Long_Gaps_Cycles","cycle"),("DMA_Busy_Inside_Gaps","cycle"),
                ("DMA_Nonbusy_Inside_Gaps","cycle"),("DMA_Submits_Inner","request")):
        both.append(metric(wave["B"][k],wave["D"][k],k,u,
                    Workload="tiled-matmul",Platform="OpenGeMM",Matrix_Size="16x16x16",Mode="D",Baseline_Mode="B",
                    Measurement_Scope="envelope inner",Evidence_Type="NEW_VERILATOR_VCD",
                    Evidence_Path="data/dma_summary.csv",Run_ID="envelope_checked_BD",Git_SHA=COMPILER,
                    Correctness="GOLDEN_PASS",Notes="Busy is interval occupancy; shorter busy is not inherently better",
                    expected="descriptive"))
        both[-1]["Benefit_or_Regression"]="DESCRIPTIVE_ONLY"
    profiles=[]
    for folder in sorted((local/"backend").iterdir()):
        for stage in ("backend","link"):
            profiles.append(dict(Order=folder.name.split("_")[0],Mode=folder.name[-1],Stage=stage,Size=16,
                                 **read_json(folder/(stage+".json"))))
    assert len(profiles)==24
    write(data/"backend_samples.csv",profiles)
    for platform,mode,revision in (("OpenGeMM","D",COMPILER),("Gemmini","dedup",GEMMINI)):
        for k,unit,comment in (
            ("Physical_Config_Byte_Traffic","byte","no device-level byte counter"),
            ("Energy","joule","no board or calibrated activity model"),
            ("Power","watt","no calibrated switching model"),
            ("Area","um^2","no physical synthesis"),
            ("Achieved_Frequency","Hz","no synthesis or board measurement"),
            ("Cache_Miss_Change","event","no cache event audit"),
            ("Compiler_Version_Sensitivity","N/A","study toolchain pinned"),
        ):
            both.append(metric("NOT MEASURED","NOT MEASURED",k,unit,Workload="all",
                               Platform=platform,Matrix_Size="N/A",Mode=mode,
                               Baseline_Mode="A" if platform=="OpenGeMM" else "baseline",
                               Measurement_Scope="N/A",Evidence_Type="NOT_MEASURABLE",
                               Evidence_Path="data/paper_metric_coverage.csv",Run_ID="N/A",
                               Git_SHA=revision,Correctness="N/A",Notes=comment))
    write(data/"multi_metric_comparison.csv",both)
    excluded={"Wall_Median","RSS_Median_KiB"}
    write(data/"regression_cases.csv",[r for r in both if r["Benefit_or_Regression"]=="REGRESSION" and r["Metric"] not in excluded])


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("data",type=Path)
    p.add_argument("local",type=Path)
    a=p.parse_args()
    run(a.data,a.local)
