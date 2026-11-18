"""Require correct numerical results, live-out, staging snapshots, and DMA handoff."""
import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
import traceback

# The parser is inherited from the unchanged P1 commit.
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root/"p1_criticalpath_pilot/scripts"))
from traces import POINTERS, counts, dma_events, read_trace, window

BRANCH = {"beq","beqz","bne","bnez","bge","bgez","bgeu","blt","bltz","bltu","bgtz","blez"}
LOAD = {"lw","lb","lbu","lh","lhu","flw"}
STORE = {"sw","sb","sh","fsw"}
ABI = {"mv","nop"}
MEMORY_WORD = re.compile(r"Word\[(0x[0-9a-f]+)\]")
MCYCLE = re.compile(r"\bmcycle = (0x[0-9a-f]+|\d+)")
HEX_KEYS = {"first_a","first_b","first_c","next_a","next_b","next_c","source"}
SCENARIOS = {0:"tensor-chain",1:"all-ready",2:"all-fields-late",3:"observable-staging"}


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=fields,lineterminator="\n",restval="N/A")
        writer.writeheader()
        writer.writerows(rows)


def markers(folder):
    records = []
    for row in (folder/"simulation.txt").read_text().splitlines():
        if not row.strip():
            continue
        label, *parts = row.split()
        if label not in {"P1_RESULT","P1_EXPECT","P2_RESULT","P2_EXPECT"}:
            continue
        values = dict(token.split("=") for token in parts)
        data = {k:int(v,16 if k in HEX_KEYS else 10) for k,v in values.items()}
        if label.endswith("RESULT"):
            meta = data
        else:
            records.append(data)
    assert len(records) == meta["steps"]
    assert all(v == 0 for k,v in meta.items() if k.endswith("errors"))
    return meta,records


def clock_at(op):
    m = MCYCLE.search(op.comment)
    return int(m[1],0) if op.mnemonic=="csrr" and op.literal=="mcycle" and m else None


def value(op, register):
    m = re.search(r"\b"+re.escape(register)+r"\s*=\s*(0x[0-9a-f]+|-?\d+)", op.comment)
    if m is None and register in {"zero","x0"}:
        return 0
    assert m, (register,op)
    return int(m[1],0)


def memory_load(op):
    m = MEMORY_WORD.search(op.comment)
    return int(m[1],16) if m and op.mnemonic in LOAD else None


def boundary_windows(folder, meta):
    hart0,hart1 = (read_trace(folder/f"trace_hart_{i:05d}.trace.txt.gz") for i in range(2))
    begin,end = (next(op.cycle for op in hart0 if clock_at(op)==meta[k]) for k in ("start","end"))
    assert end-begin == meta["cycles"] == meta["end"]-meta["start"]
    return window(hart0,begin+1,end-1),window(hart1,begin+1,end-1),begin,[op for op in hart1 if op.is_barrier]


def decode_dma(ops, transfers):
    current_source = current_dest = None
    by_submit = {request.cycle:(request,poll,idle,branch) for request,poll,idle,branch in transfers}
    decoded = []
    for op in ops:
        if op.mnemonic in {"dmsrc","dmdst"}:
            lo,hi = (r.strip() for r in op.operands.split(","))
            addr = value(op,lo)+(value(op,hi)<<32)
            if op.mnemonic=="dmsrc":
                current_source = addr
            else:
                current_dest = addr
        if op.cycle in by_submit and op is by_submit[op.cycle][0]:
            register = op.operands.split(",")[1].strip()
            decoded.append((*by_submit[op.cycle],current_source,current_dest,value(op,register)))
    assert len(decoded) == len(transfers)
    return decoded


def analyse_execution(job, family, method, mode):
    folder = job/mode
    assert (folder/"sim_exit").read_text().strip()=="0"
    meta,expected = markers(folder)
    cpu,dma,begin,dma_barriers = boundary_windows(folder,meta)
    trips = meta["steps"]
    size = meta.get("dma_bytes",4*meta.get("dma",0))
    resources = counts(cpu)
    assert resources["Launches"] == resources["Await_Sequences"] == 2*trips
    assert resources["CSR_Writes"] == resources["Await_CSRS"] == 6*trips
    transfer = decode_dma(dma,list(dma_events(dma)))
    assert len(transfer) == (trips if size else 0)
    cpu_barriers = [op for op in cpu if op.is_barrier]
    assert len(cpu_barriers) == (2*trips if size else 0)
    staged, snapshots, gemms, awaits, writes = {}, [], [], [], []
    for op in cpu:
        if op.is_write and op.csr in POINTERS:
            staged[op.csr] = op.write_value()
            writes.append(op)
        if op.is_write and op.csr == 0x3D5 and op.literal=="1":
            snapshots.append((op,tuple(staged.get(csr) for csr in POINTERS)))
        if op.is_write and op.csr == 0x3DB and op.literal=="1":
            gemms.append(op)
        if op.is_write and op.csr == 0x3D5 and op.literal=="0":
            awaits.append(op)
    assert len(snapshots) == len(gemms) == len(awaits) == 2*trips
    events = []
    for slot, exp in enumerate(expected):
        i = 2*slot
        first_stream,first_snapshot = snapshots[i]
        next_stream,next_snapshot = snapshots[i+1]
        start,ready,launch = gemms[i].cycle,awaits[i].cycle,gemms[i+1].cycle
        assert first_snapshot == tuple(exp[f"first_{key}"] for key in "abc")
        assert next_snapshot == tuple(exp[f"next_{key}"] for key in "abc")
        pending = [op for op in writes if start<op.cycle<next_stream.cycle]
        assert sorted(op.csr for op in pending) == list(POINTERS)
        moved = tuple(op.csr for op in pending if op.cycle<ready)
        if family.startswith("p1"):
            fields = POINTERS[::2]
            early = method in {"g","g-private"}
            is_input_load = True
            source = exp["first_c"] if not size else exp["first_a"]+5*(meta["K"]//8)*256+8*256+4*slot
            checked_words = 1
        else:
            scenario = meta["scenario"]
            fields = POINTERS if scenario==1 else POINTERS[1:]
            early = method=="g" or (method=="w" and scenario==1 and bool(moved))
            is_input_load = scenario!=1
            source = exp["source"]
            checked_words = 64
        assert moved == (fields if early else ()), (job,slot,moved)
        row = dict(Run_ID=job.name,Family=family,Mode=mode,Slot=slot,Selector=exp["selector"],
                   Next_A=hex(next_snapshot[0]),Next_B=hex(next_snapshot[1]),Next_C=hex(next_snapshot[2]), Begin=begin,
                   First_Stream_Launch=first_stream.cycle,First_GEMM=start,First_Await=ready,
                   A_Write=next(op.cycle for op in pending if op.csr==POINTERS[0]),
                   B_Write=next(op.cycle for op in pending if op.csr==POINTERS[1]),
                   C_Write=next(op.cycle for op in pending if op.csr==POINTERS[2]),
                   Next_Stream_Launch=next_stream.cycle,Second_GEMM=launch,Final_Await=awaits[i+1].cycle)
        if is_input_load:
            addresses = set(range(source,source+4*checked_words,4))
            relevant = [(op,memory_load(op)) for op in cpu if ready<op.cycle<next_stream.cycle]
            source_reads = [op for op,address in relevant if address in addresses]
            assert {memory_load(op) for op in source_reads} == addresses, (job,slot,len(source_reads))
            read_head,read_tail=source_reads[0].cycle,source_reads[-1].cycle
            row.update(Load_First=read_head,Load_Last=read_tail,Load_Address=hex(source),Observed_Source_Words=checked_words)
            late_fields = {POINTERS[1]} if family.startswith("p1") else ({POINTERS[0]} if meta["scenario"]!=2 else set(POINTERS))
            assert all(op.cycle>read_tail for op in pending if op.csr in late_fields)
            if method in {"g-late","l"}:
                assert all(ready<op.cycle<read_head for op in pending if op.csr in fields)
            if method in {"s","w","s-compact","s-reg","g-full-late"}:
                assert all(op.cycle>read_tail for op in pending)
        if size:
            request,first_poll,idle,branch,src,dest,amount = transfer[slot]
            left,right=cpu_barriers[2*slot:2*slot+2]
            left_dma = next(op for op in reversed(dma_barriers) if op.cycle<request.cycle)
            right_dma = next(op for op in dma_barriers if op.cycle>branch.cycle)
            if slot:
                assert events[-1]["Hart1_Give"]<left_dma.cycle
            assert (src,dest,amount) == (exp["first_c"],source,size)
            assert ready<left.cycle<request.cycle<=first_poll.cycle<=idle.cycle<read_head
            assert left_dma.cycle<request.cycle and branch.cycle<right_dma.cycle<read_head
            assert left.cycle<right.cycle<read_head and idle.cycle<read_head
            row.update(DMA_Request=request.cycle,DMA_Idle=idle.cycle,DMA_Bytes=amount,
                       Hart0_Give=left.cycle,Hart0_Receive=right.cycle,Hart1_Acquire=left_dma.cycle,Hart1_Give=right_dma.cycle)
        events.append(row)
    ops = Counter(op.mnemonic for op in cpu)
    result = dict(Run_ID=job.name,Family=family,Mode=mode,Method=method,K=meta["K"],Trips=trips,
                  Seed=meta["seed"],DMA_Bytes=size,Scenario="metadata-select" if family.startswith("p1") else SCENARIOS[meta["scenario"]],
                  Cycles=meta["cycles"],**resources,Branches=sum(ops[key] for key in BRANCH),
                  Calls=ops["jal"]+ops["jalr"],Returns=ops["ret"],
                  Loads=sum(ops[key] for key in LOAD),Stores=sum(ops[key] for key in STORE),
                  Moves=ops["mv"],Nops=ops["nop"],GEMM_Handoff_Cycles=sum(e["Second_GEMM"]-e["First_GEMM"] for e in events),
                  DMA_Request_To_Idle=sum(e["DMA_Idle"]-e["DMA_Request"] for e in events if "DMA_Idle" in e),
                  ELF_Bytes=(job/"pilot.x").stat().st_size,ELF_SHA256=sha(job/"pilot.x"),
                  Disassembly_SHA256=sha(job/"disassembly.txt"),Sim_Exit=0,Correctness="PASS")
    return result,events,meta,dict(sorted(ops.items()))


def validate_patch(job, source):
    if not (job/"patch.json").is_file():
        return
    audit = json.loads((job/"patch.json").read_text())
    original = bytearray(source.read_bytes())
    target = (job/"pilot.x").read_bytes()
    assert len(original)==len(target)==audit["bytes"]
    assert sha(source)==audit["input_sha256"] and sha(job/"pilot.x")==audit["output_sha256"]
    for word in audit["changed_words"]:
        off=word["offset"]
        assert int.from_bytes(original[off:off+4],"little")==int(word["old"],16)
        original[off:off+4]=int(word["new"],16).to_bytes(4,"little")
    assert original==target


def analyze(local, p1, report):
    results,all_events,checks,failures = [],[],[],[]
    for family in ("p1_controls","p1_edges","chain"):
        if not (local/family).is_dir():
            continue
        for job in sorted((local/family).iterdir()):
            method = job.name.split("_")[0 if family.startswith("p1") else 1]
            if (job/"patch.json").is_file():
                original = Path((job/"source_path").read_text().strip())
                original = p1/original.relative_to("/p1") if family.startswith("p1") else local/original.relative_to("/out")
                validate_patch(job,original/"pilot.x")
            elif family.startswith("p1"):
                original = p1/Path((job/"source_path").read_text().strip()).relative_to("/p1")
                assert sha(original/"pilot.x") == sha(job/"pilot.x")
            for mode in ("trace","wave"):
                if not (job/mode/"DONE").is_file():
                    continue
                try:
                    row,events,meta,op_hist = analyse_execution(job,family,method,mode)
                except (AssertionError,KeyError,StopIteration,UnboundLocalError,ValueError) as exc:
                    failures.append(dict(run=job.name,mode=mode,error=repr(exc),location=traceback.format_tb(exc.__traceback__)[-1].strip()))
                    continue
                results.append(row)
                all_events.extend(events)
                checks.append(dict(run=job.name,mode=mode,meta=meta,launch_pairs=len(events),opcode_histogram=op_hist,
                                   verified="golden, staging snapshots, write order, live-out and applicable DMA byte count/source/dest/idle"))
    write_csv(report/"data"/"performance.csv",results)
    write_csv(report/"data"/"timeline.csv",all_events)
    (report/"data"/"correctness.json").write_text(json.dumps(dict(verified=checks,failures=failures),indent=2)+"\n")
    print(f"Verified {len(results)} executions with {len(all_events)} launch pairs")
    if failures:
        for failure in failures:
            print(failure)
        return 1
    return 0


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    for name in ("local","p1","report"):
        ap.add_argument(name,type=Path)
    args=ap.parse_args()
    raise SystemExit(analyze(args.local,args.p1,args.report))
