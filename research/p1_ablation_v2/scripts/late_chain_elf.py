"""Delay only the checked early setup words in a linked chain ELF."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import struct

from rewrite_elf import AWAIT, functions, location

STEP_NAMES = ("chain_step", "_mlir_ciface_chain_step")


def delay(source, disasm, target, audit, fields):
    original = source.read_bytes()
    modified = bytearray(original)
    updated_words = []
    for symbol,(pc,words,_) in functions(disasm.read_text(),STEP_NAMES).items():
        gemm = words.index(0x3DB0D073)
        start = gemm+1
        end = start+len(fields)
        selected = words[start:end]
        assert all(w & 0xfffff == 0x01073 | ((w>>15 & 31)<<15) for w in selected), [hex(w) for w in selected]
        assert tuple(w >> 20 for w in selected) == tuple(fields)
        assert words[end:end+3] == AWAIT
        permuted = AWAIT+selected
        assert Counter(words[start:end+3]) == Counter(permuted)
        off = location(original, pc+4*start, 4*len(permuted))
        for index, (old,new) in enumerate(zip(words[start:end+3],permuted)):
            assert struct.unpack_from("<I", original, off+4*index)[0] == old
            struct.pack_into("<I",modified,off+4*index,new)
            if old != new:
                updated_words.append(dict(symbol=symbol, pc=hex(pc+4*(start+index)),
                                          offset=off+4*index, old=f"{old:08x}",new=f"{new:08x}"))
    target.write_bytes(modified)
    audit.write_text(json.dumps(dict(bytes=len(modified),input_sha256=sha256(original).hexdigest(),
                                     output_sha256=sha256(modified).hexdigest(),changed_words=updated_words),
                                indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for v in ("source","disasm","target","audit"):
        parser.add_argument(v,type=Path)
    parser.add_argument("scenario",type=int,choices=(0,1))
    m = parser.parse_args()
    delay(m.source,m.disasm,m.target,m.audit,(978,979,980) if m.scenario==1 else (979,980))
