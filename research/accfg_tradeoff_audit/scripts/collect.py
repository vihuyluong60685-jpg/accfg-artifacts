"""Reconcile retained paper traces, isolate new scopes, and extract ELF/IR metrics."""
import argparse
from collections import Counter
from hashlib import sha256
import csv
import gzip
import json
from pathlib import Path
import re
import sys

from elftools.elf.elffile import ELFFile
import pandas as pd

MODES=dict(zip(("NO_ACCFG_OPT","DEDUP_ONLY","OVERLAP_ONLY","ACCFG_BOTH"),"ABCD"))
CSR_CONFIG=set(range(0x3c0,0x3d5))|set(range(0x3d7,0x3db))
CSR_ALL=CSR_CONFIG|{0x3d5,0x3db}
BRANCH={"beq","beqz","bne","bnez","bge","bgez","bgtz","blt","bltz","blez","bgeu","bltu"}
LOAD={"lw","lh","lhu","lb","lbu","ld","flw","fld"}
STORE={"sw","sb","sh","sd","fsw","fsd"}
INSN=re.compile(r"\s*\d+\s+(\d+)\s+[A-Z]\s+(0x[0-9a-f]+)\s+(\w+)\s*([^#]*)(?:#;?\s*(.*))?")
CSR=re.compile(r"unknown_([0-9a-f]+)")
STACK=re.compile(r"[-\d]+\(sp\)$")
DIS=re.compile(r"^\s*([0-9a-f]+):\s+((?:[a-f0-9]{2} )+[a-f0-9]{2})\s+([\w.]+)\s*(.*)$")


def write(path,rows):
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields,lineterminator="\n",restval="N/A")
        writer.writeheader()
        writer.writerows(rows)


def read(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def read_json(path):
    return json.loads(path.read_text())


def file_hash(path):
    with path.open("rb") as f:
        h=sha256()
        for chunk in iter(lambda:f.read(1024**2),b""):
            h.update(chunk)
    return h.hexdigest()


def trace_window(path,start,stop):
    open_trace=gzip.open if path.suffix==".gz" else open
    with open_trace(path,"rt") as f:
        for i,line in enumerate(f,1):
            match=INSN.match(line)
            if not match:
                continue
            c,pc,op,args,comment=match.groups()
            cycle=int(c)
            if cycle>stop:
                break
            if cycle>=start:
                m=CSR.search(args)
                yield cycle,int(pc,16),op,args.strip(),comment or "",int(m[1],16) if m else None,i


def counts(ops):
    stat=Counter()
    config=[]
    launch=[]
    for cycle,pc,op,args,comment,csr,line in ops:
        stat["Host_Instructions"]+=1
        stat["Dynamic_Branches"]+=op in BRANCH
        stat["Dynamic_Loads"]+=op in LOAD
        stat["Dynamic_Stores"]+=op in STORE
        stat["SP_LoadStore"]+=op in LOAD|STORE and bool(STACK.search(args))
        if op not in {"csrw","csrwi"}:
            continue
        stat["Named_CSR_Writes_Paper_Definition"]+=csr in CSR_ALL
        if csr in CSR_CONFIG:
            config.append(cycle)
            stat["Config_CSR_Writes"]+=1
        if csr==0x3d5:
            (launch.append(cycle) if args.split(",")[-1].strip()=="1" else None)
            stat["Awaits"]+=args.split(",")[-1].strip()=="0"
    assert launch
    stat.update(Launches=len(launch),Config_Pre_First_Launch=sum(c<launch[0] for c in config),
                Config_After_Final_Launch=sum(c>launch[-1] for c in config))
    stat["CSR_Instruction_Bytes"]=4*stat["Config_CSR_Writes"]
    return dict(stat)


def static_elf(path,disassembly):
    row=dict(ELF_Bytes=path.stat().st_size,ELF_SHA256=file_hash(path))
    with path.open("rb") as f:
        elf=ELFFile(f)
        tab=elf.get_section_by_name(".symtab")
        owners={symbol.name: symbol["st_size"] for symbol in tab.iter_symbols()
                if symbol["st_info"]["type"]=="STT_FUNC" and re.fullmatch(r"(?:_mlir_ciface_)?streamer_matmul(?:_pinned(?:_1)?)?",symbol.name)}
        for label in ("text","rodata","data","bss"):
            section=elf.get_section_by_name("."+label)
            row[label.title()+"_Bytes"]=section["sh_size"] if section else 0
        row.update(Debug_Section_Bytes=sum(sec["sh_size"] for sec in elf.iter_sections() if sec.name.startswith(".debug")),
                   Kernel_Symbol_Bytes=sum(owners.values()),Timed_Kernel_Symbol_Bytes=owners.get("streamer_matmul_pinned_1"),
                   ELF_Executable_Load_File_Bytes=sum(seg["p_filesz"] for seg in elf.iter_segments()
                                                       if seg["p_type"]=="PT_LOAD" and seg["p_flags"]&1))
    current=None
    stats=Counter()
    registers=set()
    saved=[]
    restored=[]
    frames=[]
    for line in disassembly.read_text().splitlines():
        if symbol:=re.match(r"^[a-f0-9]+ <([^>]+)>:$",line):
            current=symbol[1]
        if current!="streamer_matmul_pinned_1":
            continue
        m=DIS.match(line)
        if not m:
            continue
        op,args=m[3],m[4]
        stats["Timed_Static_Instructions"]+=1
        stats["Timed_Static_Branches"]+=op in BRANCH
        stats["Timed_Static_Loads"]+=op in LOAD
        stats["Timed_Static_Stores"]+=op in STORE
        reg_pattern=r"\b(?:s(?:1[01]|[0-9])|a[0-7]|t[0-6]|sp|ra|zero)\b"
        registers.update(re.findall(reg_pattern,args))
        if op in {"addi","addiw"} and (frame:=re.fullmatch(r"sp, sp, -(\d+)",args)):
            frames.append(int(frame[1]))
        if op in LOAD|STORE and STACK.search(args):
            reg=args.split(",",1)[0]
            if re.fullmatch(r"s\d+|ra",reg):
                (saved if op in STORE else restored).append((reg,args.split(",",1)[1]))
    row.update(stats)
    row.update(Timed_Stack_Frame_Bytes=max(frames,default=0),Timed_Registers_Referenced=len(registers),
               Timed_ABI_Save_Restore_Pairs=len(set(saved)&set(restored)),
               Timed_ABI_Saved_Registers=" ".join(sorted({v[0] for v in set(saved)&set(restored)})))
    assert owners and stats["Timed_Static_Instructions"],path
    return row


def original(accepted,local):
    pkl=pd.read_pickle(accepted/"artifacts/opengemm_results.pkl")
    evidence={r["binary"]:r["binary_sha256"] for r in read(accepted/"reports/tables/opengemm_trace_audit.csv")}
    for row in sorted(pkl.to_dict("records"),key=lambda r:(r["size"],MODES[r["option"]])):
        n=int(row["size"])
        flag=row["option"]
        shape=f"{n}x{n}x{n}"
        build=f"test_generated_{shape}_{flag}"
        d=accepted/f"snax-mlir/kernels/streamer_matmul/results/tiled_matmul_generated_{shape}"/build
        trace=d/"trace_hart_00000.trace.txt"
        section=read_json(d/"trace_hart_00000.trace.json")[1]
        assert section["cycles"]==row["cycles"]
        m=counts(trace_window(trace,section["start"],section["end"]))
        assert m["Named_CSR_Writes_Paper_Definition"]==int(row["csrw"]+row["csrwi"])
        elf=static_elf(d/"generated.stream.x",local/"elf"/f"original_{build}.txt")
        assert elf["ELF_SHA256"]==evidence[str((d/"generated.stream.x").relative_to(accepted))]
        yield dict(Run_ID="paper_"+shape+"_"+MODES[flag],Scope="paper_no_copy",
                   Shape=shape,Mode=MODES[flag],Cycles=int(row["cycles"]),**m,**elf,
                   Evidence="HISTORICAL_REDECODED",Correctness="NOT_CHECKED",
                   Path=str(trace))


def new_open(local):
    for family in ("extras","envelope"):
        for d in sorted((local/family).iterdir()):
            m=re.fullmatch(r"(checked|no_copy)_(.+)_([ABCD])_r1",d.name)
            assert m,d
            scope,shape,mode=m.groups()
            if not (d/"trace/DONE").exists():
                continue
            t=d/"trace"
            section=read_json(t/"trace_hart_00000.json")[2 if family=="envelope" else 1]
            trace=t/"trace_hart_00000.gz"
            c=counts(trace_window(trace,section["start"],section["end"]))
            elf=static_elf(d/"pilot.x",local/"elf"/f"{family}_{d.name}.txt")
            ok="GOLDEN_PASS" if scope=="checked" else "NOT_CHECKED"
            evidence=dict(Run_ID=family+"_"+d.name,Scope=family+"_"+scope,Shape=shape,Mode=mode,
                          Cycles=section["cycles"],**c,**elf,Evidence="NEW_VERILATOR",Correctness=ok,
                          Path=str(trace.relative_to(local)))
            if family=="envelope":
                bounds=re.search(r"AUDIT_OUTER start=(\d+) end=(\d+) cycles=(\d+)",(t/"stdout.txt").read_text())
                a,b,v=map(int,bounds.groups())
                assert b-a==v
                evidence.update(Outer_Cycles=v,Outer_Start=a,Outer_End=b)
            yield evidence


def prior_report(p1):
    f=p1/"reports/p1_criticalpath_pilot/data/new_square_replays.csv"
    for r in read(f):
        if r["Method"] in "ABCD" and r["Scope"]=="checked":
            yield dict(Run_ID=r["Run_ID"],Scope="prior_checked",Shape=r["Matrix_Size"],Mode=r["Method"],
                       Cycles=int(r["Cycles"]),Config_CSR_Writes=int(r["CSR_Writes"]),
                       Host_Instructions=int(r["Host_Instructions"]),ELF_Bytes=int(r["ELF_Bytes"]),
                       ELF_SHA256=r["ELF_SHA256"],Evidence="PRIOR_UNMODIFIED_ABCD",Correctness="GOLDEN_PASS",Path=str(f))


def collect_gemmini(accepted,local,data):
    rows=[]
    for r in read(accepted/"reports/tables/gemmini_measured.csv"):
        rows.append(dict(Run_ID="official_"+r["size"]+"_"+r["option"],Size=int(r["size"]),
                   Scope="official_C_vs_MLIR",Mode=r["option"],Counter_Interval=int(r["cycles"]),
                   Whole_Trace_RoCC=int(r["rocc"]),ELF_SHA256=r["binary_sha256"],
                   Correctness="CHECK_DISABLED" if r["option"]=="MLIR deduplicated" else "OFFICIAL_EXIT_ZERO",
                   Model_Attainable_Ops_Per_Cycle=r["p_attain_unrounded"],Evidence="HISTORICAL_SPIKE_PLUS_MODEL"))
    for d in sorted((local/"gemmini").iterdir()):
        if not (d/"spike.json").is_file():
            continue
        size,mode,check=d.name.split("_")
        r=read_json(d/"spike.json")
        assert r["Complete"] and r["Counter_Interval"]-r["Dynamic_Inside"] in {0,1,2}
        check="GOLDEN_PASS" if r["Spike_Exit"]==0 and check=="check1" else "CHECK_DISABLED" if r["Spike_Exit"]==0 else "FAIL"
        rows.append(dict(Run_ID=d.name,Size=int(size),Scope="matched_MLIR_checked" if check=="GOLDEN_PASS" else "matched_MLIR",
                         Mode=mode,Counter_Interval=r["Counter_Interval"],Dynamic_Inside=r["Dynamic_Inside"],
                         In_Interval_RoCC=r["In_Interval_RoCC"],RoCC_Config_Funct7_0=r["RoCC_Opcode_Funct7"].get("7b:0",0),
                         ELF_SHA256=file_hash(d/"test.x"),Correctness=check,Spike_Exit=r["Spike_Exit"],Evidence="NEW_SPIKE_INSTRUCTION_TRACE"))
    write(data/"gemmini_cases.csv",rows)
    for n in (32,64,128):
        a,b=[local/"gemmini"/f"{n}_{m}_check0/common.mlir" for m in ("baseline","dedup")]
        assert a.read_bytes()==b.read_bytes()
    return rows


def compile_data(local,data):
    builds=[]
    passes=[]
    for d in sorted((local/"compile").iterdir()):
        size,mode,rep=d.name.split("_")[2:]
        m=read_json(d/"build.json")
        builds.append(dict(Size=int(size.split("x")[0]),Mode=mode,Rep=int(rep[1:]),
                           Order=int((d/"order").read_text()),Run_ID=d.name,**m))
        if (d/"passes.json").is_file():
            for row in read_json(d/"passes.json"):
                passes.append(dict(Size=int(size.split("x")[0]),Mode=mode,Run_ID=d.name,**row))
    assert len(builds)==48 and len(passes)>400
    write(data/"build_samples.csv",builds)
    write(data/"pass_samples.csv",passes)
    return builds,passes


def coverage_boundary(local,data):
    rows=[]
    for fixture in ("boundary","boundary_consumer","boundary_guarded"):
        for method in ("R" if fixture=="boundary_guarded" else "ABCD"):
            d=local/fixture/method
            if not (d/"stdout.txt").is_file():
                continue
            for line in (d/"stdout.txt").read_text().splitlines():
                if line.startswith("AUDIT_LIVE "):
                    rows.append(dict(Fixture=fixture,Mode=method,**dict(v.split("=") for v in line.split()[1:]),
                                     Verilator_Exit=(d/"sim.exit").read_text().strip()))
    assert len(rows)>=12
    write(data/"boundary_cases.csv",rows)


def main(accepted,local,p1,data):
    rows=[*original(accepted,local),*new_open(local),*prior_report(p1)]
    assert sum(r["Scope"]=="paper_no_copy" for r in rows)==24
    write(data/"opengemm_cases.csv",rows)
    collect_gemmini(accepted,local,data)
    compile_data(local,data)
    coverage_boundary(local,data)
    print("Collected",len(rows),"OpenGeMM cases")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for k in ("accepted","local","p1","data"):
        p.add_argument(k,type=Path)
    a=p.parse_args()
    main(a.accepted,a.local,a.p1,a.data)
