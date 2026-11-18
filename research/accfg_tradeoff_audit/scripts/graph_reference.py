"""Import previously verified original A/B/C graph modes as read-only reference."""
import argparse
from pathlib import Path

from collect import file_hash,read,read_json,write

p=argparse.ArgumentParser()
p.add_argument("previous",type=Path)
p.add_argument("output",type=Path)
a=p.parse_args()
report=a.previous/"reports/p1_workload_gate"
path=report/"data/execution_phases.csv"
manifest={r["Path"]:r["SHA256"] for r in read(report/"manifests/report_sha256.csv")}
for item in ("data/execution_phases.csv", "data/correctness.json", "data/performance.csv"):
    assert file_hash(report/item)==manifest[item]


def key(row):
    return row["Graph"],row["Method"],int(row["Seed"])


performance={key(r):r for r in read(report/"data/performance.csv") if r["Mode"]=="trace"}
correctness={key(r):r for r in read_json(report/"data/correctness.json") if r["Mode"]=="trace"}
rows=[]
for r in read(path):
    if r["Mode"]!="trace" or r["Method"] not in "ABC":
        continue
    v=lambda name:int(r[name])
    counters=performance[key(r)]
    result=correctness[key(r)]
    assert counters["ELF_SHA256"]==result["ELF_SHA256"]
    assert all(value==0 for name,value in result.items() if name.endswith("_errors"))
    assert int(counters["Cycles"])==v("End")-v("Start")
    rows.append(dict(Graph=r["Graph"],Mode=r["Method"],Seed=r["Seed"],Cycles=v("End")-v("Start"),
                     Config_CSR_Writes=int(counters["CSR_Writes"]),Host_Instructions=int(counters["Host_Instructions"]),
                     Correctness="GOLDEN_PASS",
                     Packing_To_First_CSR=v("Pre_Initial_Config"),
                     Initial_Dispatch=v("Initial_Config_To_Launch"),
                     First_Compute_To_Host=v("First_Launch_To_Host"),
                     Host_Middle=v("Host_Middle"),
                     Host_End_To_Second_Launch=v("Host_End_To_Second_Launch"),
                     Second_Launch_To_Await=v("Await2")-v("Next_GEMM"),
                     After_Last_Await_To_End=v("End")-v("Await2"),
                     Timed_DMA="absent",Evidence="PRIOR_READ_ONLY_GRAPH",Source=str(path)))
assert len(rows)==12
write(a.output,rows)
