"""Decode the existing Snitch instruction trace, without inventing RTL events."""
from contextlib import contextmanager
from dataclasses import dataclass
import gzip
import json
import re

INSN = re.compile(r"\s*\d+\s+(\d+)\s+[A-Z]\s+(0x[0-9a-f]+)\s+(\w+)\s*([^#]*)(?:#;?\s*(.*))?")
CSR = re.compile(r"unknown_([0-9a-f]+)")
CONFIG = set(range(0x3C0, 0x3D5)) | set(range(0x3D7, 0x3DB))
LAUNCH = {0x3D5, 0x3DB}
POINTERS = (0x3D2, 0x3D3, 0x3D4)


@dataclass(frozen=True)
class Instruction:
    cycle: int
    pc: str
    mnemonic: str
    operands: str
    comment: str
    line: int

    @property
    def csr(self):
        match = CSR.search(self.operands)
        return int(match[1], 16) if match else None

    @property
    def literal(self):
        return self.operands.split(",")[-1].strip()

    def write_value(self):
        if self.mnemonic == "csrwi":
            return int(self.literal, 0)
        if self.literal in {"zero", "x0"}:
            return 0
        match = re.search(r"\b" + re.escape(self.literal) + r"\s+=\s+(-?\d+|0x[0-9a-f]+)", self.comment)
        # Hex is also handled separately because the trace omits leading zeros.
        hex_match = re.search(r"\b" + re.escape(self.literal) + r"\s+=\s+(0x[0-9a-f]+)", self.comment)
        if hex_match:
            return int(hex_match[1], 16)
        if match:
            return int(match[1], 0)
        return None

    @property
    def is_write(self):
        return self.mnemonic in {"csrw", "csrwi"}

    @property
    def is_barrier(self):
        return self.mnemonic in {"csrs", "csrr"} and self.csr == 0x7C2


@contextmanager
def open_trace(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as stream:
            yield stream
    else:
        with path.open() as stream:
            yield stream


def read_trace(path):
    entries = []
    with open_trace(path) as stream:
        for line_number, text in enumerate(stream, 1):
            match = INSN.match(text)
            if match:
                cycle, pc, mnemonic, operands, comment = match.groups()
                entries.append(Instruction(int(cycle), pc, mnemonic, operands.strip(),
                                           comment or "", line_number))
    return entries


def section(path, index=1):
    sections = json.loads(path.read_text())
    return sections[index]


def window(entries, start, end):
    return [op for op in entries if start <= op.cycle <= end]


def counts(entries):
    return {
        "CSR_Writes": sum(op.is_write and op.csr in CONFIG for op in entries),
        "Host_Instructions": len(entries),
        "Launches": sum(op.is_write and op.csr == 0x3DB and op.literal == "1" for op in entries),
        "Launch_CSRS": sum(op.is_write and op.csr in LAUNCH and op.literal == "1" for op in entries),
        "Await_Sequences": sum(op.is_write and op.csr == 0x3D5 and op.literal == "0" for op in entries),
        "Await_CSRS": sum(op.is_write and op.csr in LAUNCH and op.literal == "0" for op in entries),
        "Barrier_CSRS": sum(op.is_barrier for op in entries),
    }


def dma_events(entries):
    """Yield request/first poll/last idle poll grouped by serialized requests."""
    request = None
    for index, op in enumerate(entries):
        if op.mnemonic.startswith("dmcpy"):
            request = op
            first = None
        if op.mnemonic != "dmstati" or op.literal != "2" or request is None:
            continue
        if first is None:
            first = op
        branch = entries[index + 1] if index + 1 < len(entries) else None
        if branch and branch.mnemonic in {"bne", "bnez"} and re.search(r"\bt0\s+=\s+0\b", branch.comment):
            yield request, first, op, branch
            request = None
