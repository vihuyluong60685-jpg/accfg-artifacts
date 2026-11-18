"""Validate all checked probe outputs against independent operand and ordering evidence."""
import argparse
from collections import defaultdict
from pathlib import Path
import re

from compare_square import COMPILER_SHA, save, sha
from traces import counts, dma_events, POINTERS, read_trace, window


def parse_row(lines, heading, hexadecimal=()):
    line = next((line for line in lines if line.startswith(heading + " ")), None)
    if not line:
        raise ValueError(f"Missing {heading}")
    return {k: int(v, 16) if k in hexadecimal else int(v)
            for k, v in (part.split("=") for part in line.split()[1:])}


def verification(folder, method, meta, expected):
    paths = [folder / f"trace_hart_{hart:05d}.trace.txt.gz" for hart in (0, 1)]
    traced = [read_trace(path) for path in paths]

    def read_counter(op):
        if op.mnemonic == "csrr" and op.literal == "mcycle":
            match = re.search(r"\bmcycle = (0x[0-9a-f]+|\d+)", op.comment)
            return int(match[1], 0) if match else None
        return None

    boundaries = [next(op for op in traced[0] if read_counter(op) == meta[k])
                  for k in ("start", "end")]
    assert boundaries[1].cycle - boundaries[0].cycle == meta["cycles"]
    cpu, dma = [window(trace, boundaries[0].cycle+1, boundaries[1].cycle-1) for trace in traced]
    resources = counts(cpu)
    assert resources["Launches"] == resources["Await_Sequences"] == 2*meta["steps"]
    assert resources["Await_CSRS"] == 6*meta["steps"]
    assert resources["CSR_Writes"] == 6*meta["steps"]
    transfers = list(dma_events(dma))
    assert len(transfers) == meta["dma"]*meta["steps"]

    step_symbol = re.search(r'^([0-9a-f]+) <_mlir_ciface_pilot_late_b>:', (folder / "disassembly.txt").read_text(), re.M)
    entries = re.findall(r'^([0-9a-f]+) <[^>]+>:', step_symbol.string[step_symbol.end():], re.M)
    lo, hi = int(step_symbol[1], 16), int(entries[0], 16)
    reads = []
    staged = {}
    writes = []
    snaps = []
    gemm = []
    await_end = []
    for op in cpu:
        if lo <= int(op.pc, 16) < hi and op.mnemonic == "lw":
            addr = re.search(r"Word\[(0x[0-9a-f]+)\]", op.comment)
            if addr:
                reads.append((int(addr[1], 16), op))
        if op.is_write and op.csr in POINTERS:
            value = op.write_value()
            assert value is not None
            staged[op.csr] = value
            writes.append(op)
        if op.is_write and op.csr == 0x3D5 and op.literal == "1":
            snaps.append((tuple(staged.get(addr) for addr in POINTERS), op))
        if op.is_write and op.csr == 0x3DB and op.literal == "1":
            gemm.append(op)
        if op.is_write and op.csr == 0x3D5 and op.literal == "0":
            await_end.append(op)
    assert len(snaps) == len(gemm) == len(await_end) == 2*len(expected)
    rows = []
    for index, exp in enumerate(expected):
        first, second = snaps[2*index:2*index+2]
        first_launch = gemm[2*index]
        first_await = await_end[2*index]
        assert first[0] == tuple(exp[f"first_{key}"] for key in "abc")
        assert second[0] == tuple(exp[f"next_{key}"] for key in "abc")

        # Five input buffers (two A, three B) and eight 256-byte output tiles
        # precede the copied words in the C workspace.
        addr = exp["first_c"]
        if meta["dma"]:
            addr = exp["first_a"] + 5 * (meta["K"]//8) * 256 + 8*256 + 4*index
        read = next(op for actual_addr, op in reads
                    if actual_addr == addr and first_await.cycle < op.cycle < second[1].cycle)
        moved = [op for op in writes if first_launch.cycle < op.cycle < first_await.cycle]
        later = [op for op in writes if read.cycle < op.cycle < second[1].cycle]
        assert [op.csr for op in moved] == (list(POINTERS[::2]) if method == "G" else [])
        assert [op.csr for op in later] == ([POINTERS[1]] if method == "G" else list(POINTERS))
        dma_cycles = {}
        if meta["dma"]:
            submit, first_poll, idle, branch = transfers[index]
            assert first_await.cycle < submit.cycle <= first_poll.cycle <= idle.cycle < read.cycle
            dma_cycles = {"DMA_Submit": submit.cycle, "DMA_Idle_Poll": idle.cycle, "DMA_Exit_Branch": branch.cycle}
        rows.append(dict(Run_ID=folder.name, Slot=index, Selector=exp["selector"],
                         First_Launch=first_launch.cycle, First_Stream_Launch=first[1].cycle,
                         A_C_Early_Write_Cycles=" ".join(str(op.cycle) for op in moved),
                         First_Last_Await_CSR=first_await.cycle, **dma_cycles,
                         Loaded_Address=hex(addr), Load_Cycle=read.cycle, Load_Line=read.line,
                         B_Write_Cycle=next(op.cycle for op in later if op.csr==POINTERS[1]),
                         Next_Stream_Launch=second[1].cycle, Next_GEMM_Launch=gemm[2*index+1].cycle,
                         Next_B=hex(second[0][1]),
                         First_ABC=" ".join(map(hex, first[0])), Second_ABC=" ".join(map(hex, second[0])),
                         Evidence="software-visible staging snapshot; every output checked"))
    return resources, rows, (gemm[0].cycle, await_end[0].cycle) if gemm else (None, None)


def analyze(local, report):
    partial = local / "partial"
    rows, snapshots, grouped = [], [], defaultdict(dict)
    for folder in sorted(partial.iterdir()):
        if not (folder / "DONE").is_file():
            continue
        method = folder.name[0]
        repeat = int(folder.name.rsplit("r", 1)[1])
        output = (folder / "simulation.txt").read_text().splitlines()
        meta = parse_row(output, "P1_RESULT")
        assert int((folder / "sim_exit").read_text()) == meta["errors"] == meta["live_errors"] == 0
        expected = [parse_row([line], "P1_EXPECT", ("first_a", "first_b", "first_c", "next_a", "next_b", "next_c"))
                    for line in output if line.startswith("P1_EXPECT ")]
        assert len(expected) == meta["steps"]
        resources, per_step, overlap_window = verification(folder, method, meta, expected)
        snapshots.extend(per_step)
        variant_row = dict(Run_ID=folder.name, Evidence="NEW", Matrix_Size=f"8x{meta['K']}x8",
                           Scope="metadata_dma_checked" if meta["dma"] else "direct_checked",
                           K=meta["K"], Trips=meta["steps"], Seed=meta["seed"], Repeat=repeat, Method=method,
                           Correctness="golden+liveout+launch-snapshots", Cycles=meta["cycles"], **resources,
                           Allocated_Input_Choices=meta["choices"], Simulator_Exit=0, Verifier_Exit=0,
                           ELF_Bytes=int((folder / "elf.bytes").read_text()),
                           Build_Ms=int((folder / "build_ms").read_text()),
                           ELF_SHA256=(folder / "elf.sha256").read_text().split()[0],
                           Compiler_Source_SHA=COMPILER_SHA, Fixture_SHA256=sha(folder / "input.mlir"),
                           Golden_Implementation="python_fixture" if (folder / "pilot_golden.h").is_file() else "c_dot_product",
                           DMA="hart1 4-byte DMA plus two barriers per trip" if meta["dma"] else "off in timed window",
                           Lowered_SHA256=sha(folder / "lowered.mlir"),
                           Trial_Class="replay" if repeat==2 else (
                               "calibration" if meta["seed"]==3 else ("heldout" if meta["steps"]==3 else "edge")),
                           First_Launch_To_Last_Await=overlap_window[1]-overlap_window[0] if meta["steps"] else 0)
        if method == "W":
            assert "Op with effects in use-def chain" in (folder/"commands.log").read_text()
        group = (variant_row["Scope"], meta["K"], meta["steps"], meta["seed"], repeat)
        grouped[group][method] = variant_row
        rows.append(variant_row)

    for (scope, k, trips, seed, repeat), variants in grouped.items():
        if "S" not in variants:
            continue
        serial = variants["S"]
        best = min(r["Cycles"] for r in variants.values())
        for method, row in variants.items():
            row.update(Speedup_vs_Matched_S=serial["Cycles"]/row["Cycles"],
                       Speedup_vs_Both="N/A", Regret=(row["Cycles"]-best)/best)
            if method == "W":
                assert row["Lowered_SHA256"] == serial["Lowered_SHA256"] and row["Cycles"] == serial["Cycles"]
            if repeat == 2:
                first = grouped[scope, k, trips, seed, 1][method]
                for field in ("ELF_SHA256","Cycles","CSR_Writes","Host_Instructions"):
                    assert row[field] == first[field], (scope,k,method,field)
    save(report / "data/partial_comparison.csv", rows)
    save(report / "data/partial_launch_snapshots.csv", snapshots)
    print(f"Verified {len(rows)} partial-run results and {len(snapshots)} checked pairs of launch snapshots")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("local", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    analyze(args.local, args.report)
