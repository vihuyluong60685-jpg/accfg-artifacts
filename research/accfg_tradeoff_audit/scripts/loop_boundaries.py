"""Measure static config footprint and trace-derived launch-prefix and tail blocks."""
import argparse
from pathlib import Path
import re

from collect import CSR_CONFIG, DIS, read, read_json, trace_window, write


def static_config_pcs(path):
    pcs = set()
    selected = False
    for line in path.read_text().splitlines():
        if header := re.fullmatch(r"[a-f0-9]+ <([^>]+)>:", line):
            selected = header[1] == "streamer_matmul_pinned_1"
        if selected and (inst := DIS.match(line)):
            encoding = bytes.fromhex(inst[2])
            if len(encoding) != 4:
                continue
            word = int.from_bytes(encoding, "little")
            opcode = word & 0x7f
            funct3 = (word >> 12) & 7
            destination = (word >> 7) & 31
            if opcode == 0x73 and funct3 in {1, 5} and destination == 0 and (word >> 20) in CSR_CONFIG:
                pcs.add(int(inst[1], 16))
    return pcs


def summarize(raw, local):
    path = Path(raw["Path"])
    timing = read_json(path.with_suffix(".json"))[1]
    stream = list(trace_window(path, timing["start"], timing["end"]))
    launches = [index for index, (_, _, _, args, _, csr, _) in enumerate(stream)
                if csr == 0x3d5 and args.split(",")[-1].strip() == "1"]
    assert launches
    first, last = launches[0], launches[-1]
    config_pcs = static_config_pcs(local/"elf"/f"original_{path.parent.name}.txt")
    before, after = stream[:first], stream[last+1:]
    before_config = {pc for _, pc, op, _, _, csr, _ in before if csr in CSR_CONFIG and op in {"csrw", "csrwi"}}
    after_config = {pc for _, pc, op, _, _, csr, _ in after if csr in CSR_CONFIG and op in {"csrw", "csrwi"}}
    assert before_config | after_config <= config_pcs
    return dict(Run_ID=raw["Run_ID"],Shape=raw["Shape"],Mode=raw["Mode"],
                Static_Config_Writes=len(config_pcs),Static_Config_Encoding_Bytes=4*len(config_pcs),
                Before_First_Launch_Executed_Insns=len(before),
                Before_First_Launch_Unique_Config_Bytes=4*len(before_config),
                After_Last_Launch_Executed_Insns=len(after),
                After_Last_Launch_Unique_Config_Bytes=4*len(after_config),
                Config_PCs_Shared_Between_Prefix_And_Tail=len(before_config & after_config),
                Launches=len(launches))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("cases", "local", "output"):
        parser.add_argument(arg, type=Path)
    args = parser.parse_args()
    rows = [summarize(row, args.local) for row in read(args.cases) if row["Scope"]=="paper_no_copy"]
    assert len(rows) == 24
    write(args.output, rows)
