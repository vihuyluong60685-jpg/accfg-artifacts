"""Reorder linked ACCFG words only inside two vetted straight-line slots."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"p1_ablation_v2/scripts"))
from rewrite_elf import AWAIT, functions, location

NAMES = ("gate_graph","_mlir_ciface_gate_graph")
PTRS = (978,979,980)
LAUNCH_GEMM = 0x3DB0D073


def permute(source,disas,target,audit,mask):
    original=source.read_bytes()
    modified=bytearray(original)
    changes=[]
    sites=[]
    symbols=functions(disas.read_text(),NAMES)
    wrapper_pc,wrapper,listing=symbols[NAMES[1]]
    entry=symbols[NAMES[0]][0]
    if len(wrapper)==1:
        assert f"0x{entry:x} <gate_graph>" in listing and wrapper[0] & 0xfff == 0x06f, wrapper_pc
        del symbols[NAMES[1]]
    for name,(pc,words,_) in symbols.items():
        assert words.count(LAUNCH_GEMM)==2
        begin=words.index(LAUNCH_GEMM)+1
        original_slot=words[begin:begin+6]
        ptrs=original_slot[:3]
        assert all(word & 0x7fff == 0x1073 for word in ptrs)
        assert tuple(word>>20 for word in ptrs)==PTRS and original_slot[3:]==AWAIT
        early=[word for i,word in enumerate(ptrs) if mask & (1<<i)]
        late=[word for i,word in enumerate(ptrs) if not mask & (1<<i)]
        ordered=early+AWAIT+late
        assert Counter(ordered)==Counter(original_slot)
        slot_pc=pc+4*begin
        offset=location(original,slot_pc,24)
        assert tuple(original_slot)==struct.unpack_from("<6I",original,offset)
        sites.append(dict(symbol=name,pc=hex(slot_pc),offset=offset,
                          prior=[f"{word:08x}" for word in original_slot],
                          current=[f"{word:08x}" for word in ordered]))
        for i,(old,new) in enumerate(zip(original_slot,ordered,strict=True)):
            struct.pack_into("<I",modified,offset+4*i,new)
            if old!=new:
                changes.append(offset+4*i)
    target.write_bytes(modified)
    audit.write_text(json.dumps(dict(mask=mask,bytes=len(original),
               old_sha=sha256(original).hexdigest(),new_sha=sha256(modified).hexdigest(),
               changed_word_offsets=changes,sites=sites),indent=2)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("source","disasm","target","audit"):
        p.add_argument(arg,type=Path)
    p.add_argument("mask",type=int,choices=range(7))
    args=p.parse_args()
    permute(args.source,args.disasm,args.target,args.audit,args.mask)
