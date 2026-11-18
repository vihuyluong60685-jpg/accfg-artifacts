"""Length-preserving rewrites of the pinned RV32 pilot's own executable code."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
import struct

STEP_NAMES = ("pilot_step", "_mlir_ciface_pilot_step")
HELPER = "_mlir_ciface_pilot_late_b"
NOP = 0x00000013
RET = 0x00008067
AWAIT = [0x3DB05073, 0x3DB05073, 0x3D505073]
EARLY_AC = [0x3D269073, 0x3D481073]
SAVE_S = [0x00812423, 0x00912223, 0x00080413, 0x00068493]
LOAD_S = [0x00812403, 0x00412483]
LATE_S = [0x3D249073, 0x3D351073, 0x3D441073]
LATE_COMPACT = [EARLY_AC[0], LATE_S[1], EARLY_AC[1]]
ARG_SLOT = 0x00088693
ARG_PRIVATE_SLOT = (ARG_SLOT & ~(31 << 7)) | (28 << 7)


def location(image, pc, size):
    assert image[:6] == b"\x7fELF\x01\x01" and struct.unpack_from("<H", image, 18)[0] == 243
    start, length, count = struct.unpack_from("<I10xHH", image, 28)
    for index in range(count):
        typ, off, addr, _, size_file, _, flags, _ = struct.unpack_from("<8I", image, start + length*index)
        if typ == 1 and flags & 1 and addr <= pc and pc+size <= addr+size_file:
            return off+pc-addr
    raise ValueError(f"Function 0x{pc:x} is not in an executable segment")


def functions(disassembly, names=(*STEP_NAMES, HELPER)):
    labels = list(re.finditer(r"^([0-9a-f]+) <([^>]+)>:\s*$", disassembly, re.M))
    selected = {}
    for index, label in enumerate(labels):
        name = label[2]
        if name not in names:
            continue
        end = labels[index+1].start() if index+1 < len(labels) else len(disassembly)
        body = disassembly[label.end():end]
        instructions = re.findall(r"^\s*([0-9a-f]+):\s*((?:[0-9a-f]{2} ){3}[0-9a-f]{2})\s+(.+)$", body, re.M)
        assert instructions
        pc = int(label[1], 16)
        words = [int.from_bytes(bytes.fromhex(code), "little") for _, code, _ in instructions]
        assert all(int(addr,16) == pc+4*i for i,(addr,_,_) in enumerate(instructions))
        selected[name] = (pc, words, body)
    assert set(selected) == set(names)
    return selected


def jal_target(word, pc):
    assert word & 0xfff == 0x0ef
    offset = ((word >> 31) << 20) | (((word >> 12) & 255) << 12) | (((word >> 20) & 1) << 11) | (((word >> 21) & 1023) << 1)
    return pc + (offset-2**21 if offset >= 2**20 else offset)


def encode_jal(target, pc):
    offset = target - pc
    assert offset % 2 == 0 and -2**20 <= offset < 2**20
    offset &= 2**21-1
    return (offset >> 20) << 31 | ((offset >> 1) & 1023) << 21 | ((offset >> 11) & 1) << 20 | ((offset >> 12) & 255) << 12 | 0xef


def change_helper(words, body):
    # The two known leaf variants use a3 only for slot/temporary, do not use
    # t3, and preserve a6. Relabel that register without touching branch PCs.
    assert len(words) in {6, 14} and words[-1] == RET
    assert not re.search(r"\b(t3|a6)\b", body)
    positions = {0x03: (7,15), 0x13: (7,15), 0x17: (7,), 0x33: (7,15,20),
                 0x37: (7,), 0x63: (15,20), 0x67: (7,15), 0x73: (7,15)}
    out = words.copy()
    for i, word in enumerate(words):
        for shift in positions[word & 127]:
            if (word >> shift) & 31 == 13:
                out[i] = (out[i] & ~(31 << shift)) | (28 << shift)
    assert out != words
    return out


def rewrite_step(words, pc, helper, method):
    # A mov a3,a7 immediately precedes the sole call. Each known function is
    # straight line around the warm and late staging slots.
    calls = [i for i, w in enumerate(words) if w & 127 == 0x6f]
    assert len(calls) == 1 and not any(w & 127 == 0x63 for w in words)
    call = calls[0]
    assert words[call-1] == ARG_SLOT and jal_target(words[call], pc + 4*call) == helper
    assert words[-1] == RET
    updated = words.copy()
    if method == "g-late":
        begin = call-9
        assert words[begin:begin+5] == EARLY_AC+AWAIT
        updated[begin:begin+5] = AWAIT+EARLY_AC
        assert Counter(updated) == Counter(words)
    elif method in {"g-private", "g-full-late"}:
        begin = call-9
        assert words[begin:begin+5] == EARLY_AC+AWAIT and words[call+1] == LATE_S[1]
        updated[call-1] = ARG_PRIVATE_SLOT
        if method == "g-full-late":
            updated[begin:call+2] = updated[begin+2:call+2]+EARLY_AC
            updated[call-2] = encode_jal(helper, pc+4*(call-2))
    else:
        assert words[2:6] == SAVE_S and words[-4:-2] == LOAD_S
        assert words[call+1:call+4] == LATE_S
        updated[call-1] = ARG_PRIVATE_SLOT
        updated[call+1:call+4] = LATE_COMPACT
        if method == "s-reg":
            updated[2:6] = [NOP]*4
            updated[-4:-2] = [NOP]*2
        else:
            del updated[-4:-2]
            del updated[2:6]
            updated[call-4] = encode_jal(helper, pc+4*(call-4))
            updated += [NOP]*6
    new_calls = [i for i,w in enumerate(updated) if w & 127 == 0x6f]
    assert len(new_calls) == 1 and jal_target(updated[new_calls[0]], pc+4*new_calls[0]) == helper
    assert len(updated) == len(words)
    return updated


def rewrite(source, disassembly, method, output, audit):
    before = source.read_bytes()
    after = bytearray(before)
    program = functions(disassembly.read_text())
    hpc = program[HELPER][0]
    rows = []
    for name, (pc, words, body) in program.items():
        if name == HELPER:
            updated = words if method == "g-late" else change_helper(words, body)
        else:
            updated = rewrite_step(words, pc, hpc, method)
        offset = location(before, pc, 4*len(words))
        assert struct.unpack_from(f"<{len(words)}I", before, offset) == tuple(words)
        for index, (old, new) in enumerate(zip(words, updated)):
            if old != new:
                struct.pack_into("<I", after, offset+4*index, new)
                rows.append(dict(symbol=name, pc=hex(pc+4*index), offset=offset+4*index,
                                 old=f"{old:08x}", new=f"{new:08x}"))
    if method != "g-late":
        # Only the two statically resolved call sites may enter the modified leaf.
        calls = re.findall(r"^\s*[0-9a-f]+:.*\bjal\s+[^\n]*<_mlir_ciface_pilot_late_b>\s*$",
                           disassembly.read_text(), re.M)
        assert len(calls) == 2
    assert len(after) == len(before) and rows
    output.write_bytes(after)
    audit.write_text(json.dumps(dict(method=method, input_sha256=sha256(before).hexdigest(),
                                     output_sha256=sha256(after).hexdigest(), bytes=len(after),
                                     changed_words=rows), indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("method", choices=("g-late","g-private","g-full-late","s-reg","s-compact"))
    for name in ("source","disassembly","output","audit"):
        parser.add_argument(name, type=Path)
    options = parser.parse_args()
    rewrite(options.source, options.disassembly, options.method, options.output, options.audit)
