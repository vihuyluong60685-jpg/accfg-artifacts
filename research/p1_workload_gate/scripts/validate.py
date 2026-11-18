"""Require both complete graph numerics and all hardware launch fields."""
import argparse
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
import sys

base=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(base/"p1_criticalpath_pilot/scripts"),str(base/"p1_ablation_v2/scripts")]
from rewrite_elf import functions
from traces import POINTERS, counts, read_trace, window
from verify_runs import BRANCH, clock_at
from generate import FIELD_VALUES, SEEDS

GRAPHS=("mobile","attention")
METHODS=("A","B","C",*(f"M{i}" for i in range(7)))
CSRS=tuple(range(960,981))+tuple(range(983,987))
FIXED={csr:value for csr,value in zip(CSRS,FIELD_VALUES.values(),strict=True) if value is not None}
HELPER="_mlir_ciface_publish_middle"


def csv_save(path,rows):
    with path.open("w",newline="") as stream:
        fields=list(dict.fromkeys(key for row in rows for key in row))
        writer=csv.DictWriter(stream,fieldnames=fields,lineterminator="\n",restval="N/A")
        writer.writeheader()
        writer.writerows(rows)


def hash_file(path):
    return sha256(path.read_bytes()).hexdigest()


def read_records(path):
    results=[]
    for line in path.read_text().splitlines():
        if line.startswith("GATE "):
            values=dict(item.split("=") for item in line.split()[1:])
            results.append({k:int(v,16 if k.startswith(("first_","next_")) else 10) for k,v in values.items()})
    assert tuple(v["seed"] for v in results)==SEEDS
    return results


def audit_patch(c,job):
    original=(c/"gate.x").read_bytes()
    audit=json.loads((job/"patch.json").read_text())
    reconstructed=bytearray(original)
    for site in audit["sites"]:
        off=site["offset"]
        assert tuple(int(x,16) for x in site["prior"])==struct.unpack_from("<6I",original,off)
        struct.pack_into("<6I",reconstructed,off,*(int(x,16) for x in site["current"]))
    assert len(reconstructed)==audit["bytes"] and bytes(reconstructed)==(job/"gate.x").read_bytes()
    assert audit["old_sha"]==hash_file(c/"gate.x") and audit["new_sha"]==hash_file(job/"gate.x")


def scope_ops(meta,trace,hart1):
    begin,end=(next(op.cycle for op in trace if clock_at(op)==meta[k]) for k in ("start","end"))
    assert end-begin == meta["end"]-meta["start"] == meta["cycles"]
    assert not any(op.mnemonic.startswith("dmcpy") for op in window(hart1,begin,end))
    return begin,end,window(trace,begin+1,end-1)


def verify(job,graph,method,mode):
    folder=job/mode
    assert (folder/"DONE").is_file() and (folder/"sim.exit").read_text().strip()=="0"
    if mode=="wave":
        assert (folder/"filter.exit").read_text().strip()=="0"
        assert read_records(folder/"simulation.txt")==read_records(job/"trace"/"simulation.txt")
    hart0,hart1=(read_trace(folder/f"trace_hart_{i:05d}.trace.txt.gz") for i in range(2))
    elf=hash_file(job/"gate.x")
    disas=(job/"disassembly.txt").read_text()
    helper_pc,helper_words,text=functions(disas,(HELPER,))[HELPER]
    assert not re.search(r"\b(csr\w*|ecall|jalr|jal)\s",text), (graph,method)
    results,trail,correct=[],[],[]
    for m in read_records(folder/"simulation.txt"):
        assert m["errors"]==m["live_errors"]==0
        begin,end,body=scope_ops(m,hart0,hart1)
        metrics=counts(body)
        assert metrics["Launches"]==metrics["Await_Sequences"]==2
        assert metrics["Await_CSRS"]==6 and metrics["Barrier_CSRS"]==0
        assert metrics["CSR_Writes"]== (50 if method=="A" else 28)
        staging={}
        streams,kernels,awaits,writes=[],[],[],[]
        for op in body:
            if op.is_write and op.csr in CSRS:
                v=op.write_value()
                assert v is not None
                writes.append(op)
                staging[op.csr]=v
            if op.is_write and op.csr==981 and op.literal=="1":
                streams.append((op.cycle,staging.copy()))
            if op.is_write and op.csr==987 and op.literal=="1":
                kernels.append((op.cycle,staging.copy()))
            if op.is_write and op.csr==981 and op.literal=="0":
                awaits.append(op.cycle)
        assert len(streams)==len(kernels)==len(awaits)==2
        for index,key in enumerate(("first","next")):
            expected=dict(FIXED)
            expected.update({csr:m[f"{key}_{field}"] for field,csr in zip("abc",POINTERS,strict=True)})
            assert streams[index][1]==kernels[index][1]==expected
        first_kern=kernels[0][0]
        writes2=[op for op in writes if first_kern<op.cycle<streams[1][0]]
        early=[op for op in writes2 if op.cycle<awaits[0]]
        nominal=7 if method=="C" else int(method[1:]) if method.startswith("M") else 0
        mask=sum(1<<POINTERS.index(op.csr) for op in early)
        assert mask==nominal and all(op.csr in POINTERS for op in early)
        helper=[op for op in body if helper_pc<=int(op.pc,16)<helper_pc+4*len(helper_words)]
        assert helper and awaits[0]<helper[0].cycle<=helper[-1].cycle<streams[1][0]
        tensor=set(range(m["first_c"],m["first_c"]+256,4))
        addresses={int(match[1],16) for op in helper if op.mnemonic=="lw"
                   for match in re.finditer(r"Word\[(0x[0-9a-f]+)\]",op.comment)}
        assert tensor<=addresses, (graph,method,len(tensor & addresses))
        phases=dict(Pre_Initial_Config=writes[0].cycle-begin,
                    Initial_Config_To_Launch=first_kern-writes[0].cycle,
                    First_Launch_To_Host=helper[0].cycle-first_kern,
                    Host_Middle=helper[-1].cycle-helper[0].cycle,
                    Host_End_To_Second_Launch=kernels[1][0]-helper[-1].cycle,
                    Second_Launch_To_End=end-kernels[1][0])
        assert sum(phases.values())==m["cycles"]
        branch_encoding=[(op.pc,body[i+1].pc) for i,op in enumerate(body[:-1]) if op.mnemonic in BRANCH]
        sig=sha256(json.dumps(branch_encoding,separators=(",",":")).encode()).hexdigest()
        result=dict(Graph=graph,Method=method,Mode=mode,Seed=m["seed"],Cycles=m["cycles"],**metrics,
                    Early_Mask=mask,Early_CSRs=len(early),Branch_Path_SHA256=sig,
                    ELF_SHA256=elf,ELF_Bytes=(job/"gate.x").stat().st_size,Simulator_Exit=0,Correctness="PASS")
        results.append(result)
        clock=dict(Graph=graph,Method=method,Mode=mode,Seed=m["seed"],Start=begin,End=end,
                   First_Streamer=streams[0][0],First_GEMM=first_kern,Await1=awaits[0],
                   Host_Begin=helper[0].cycle,Host_End=helper[-1].cycle,Next_Streamer=streams[1][0],
                   Next_GEMM=kernels[1][0],Await2=awaits[1],**phases)
        for letter,csr in zip("ABC",POINTERS,strict=True):
            change,=[op for op in writes2 if op.csr==csr]
            clock["Write_"+letter]=change.cycle
            clock["Next_"+letter]=hex(m["next_"+letter.lower()])
        trail.append(clock)
        correct.append(dict(**{k:result[k] for k in ("Graph","Method","Mode","Seed","ELF_SHA256")},
                            producer_errors=0,host_errors=0,consumer_errors=0,final_errors=0,live_csr_errors=0,
                            compared_tensor_elements=256,source_words_confirmed=64,full_launch_snapshots=2,
                            CSR_values_per_snapshot=25,ordered_waits=2,timed_DMA_requests=0,
                            golden_errors_source="aggregate zero from target elementwise oracle"))
    return results,trail,correct


def main(local,out):
    results,trail,correct=[],[],[]
    for graph in GRAPHS:
        for method in METHODS:
            job=local/graph/method
            assert (job/"build.exit").read_text().strip()=="0"
            if method.startswith("M"):
                audit_patch(local/graph/"C",job)
            for mode in ("trace","wave"):
                if mode=="wave" and method not in {"C","M0"}:
                    continue
                run_timings,events,check=verify(job,graph,method,mode)
                results.extend(run_timings)
                trail.extend(events)
                correct.extend(check)
    for graph in GRAPHS:
        for seed in SEEDS:
            same_layout=[r for r in results if r["Graph"]==graph and r["Mode"]=="trace"
                         and r["Seed"]==seed and r["Method"] not in {"A","B"}]
            assert len(same_layout)==8
            for key in ("Host_Instructions","CSR_Writes","ELF_Bytes","Branch_Path_SHA256"):
                assert len({r[key] for r in same_layout})==1,(graph,seed,key)
    csv_save(out/"performance.csv",results)
    csv_save(out/"execution_phases.csv",trail)
    (out/"correctness.json").write_text(json.dumps(correct,indent=2)+"\n")
    print(f"Validated {len(results)} graph invocations and {2*len(results)} full CSR snapshots")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("local",type=Path)
    p.add_argument("data",type=Path)
    setup=p.parse_args()
    main(setup.local,setup.data)
