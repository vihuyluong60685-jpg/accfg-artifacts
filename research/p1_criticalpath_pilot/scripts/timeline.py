"""Extract barrier windows and DMA handoff evidence from the retained dual-hart traces."""
import argparse
import json
from pathlib import Path

from compare_square import save, sha
from traces import CONFIG, LAUNCH, dma_events, read_trace, section, window

CSR_SOURCE = "/opt/snax-streamer-gemm/target/snitch_cluster/sw/snax/streamer-gemm/src/snax-streamer-gemm-lib.c"


def diagnose(accepted, report):
    previous = accepted / "reports/research_opportunities/diagnostics"
    raw = previous / "rtl_reference_raw"
    digests = json.loads((previous / "run_context.json").read_text())["diagnostic_files_sha256"]
    events = []
    stages = []
    summary = []
    edges = []

    for variant, expected in (("original", 1521), ("guard", 1549), ("omit", 1560)):
        files = [raw / f"checked_{variant}_trace_hart_{hart}.trace.txt.gz" for hart in ("00000", "00001")]
        part_file = raw / f"checked_{variant}_trace_hart_00000.trace.json"
        for path in (*files, part_file):
            assert sha(path) == digests[str(path.relative_to(previous))]
        part = section(part_file)
        start, end = part["start"], part["end"]
        harts = [window(read_trace(f), start, end) for f in files]
        marked = {}

        def emit(kind, hart, op=None, *, dep="", duration="", level="MEASURED",
                 resource="", evidence="", detail="", cycle=None):
            event_id = f"{variant}/{len(events)+1}"
            source = str(files[hart].relative_to(accepted)) if op is not None else str(part_file.relative_to(accepted))
            events.append(dict(Run_ID=f"historical_checked16_{variant}", Event_ID=event_id,
                               Variant=variant, Matrix_Size="16x16x16", Scope="checked",
                               Hart=hart if hart is not None else "", Event_Type=kind,
                               Cycle=op.cycle if op is not None else cycle, Event_Duration=duration,
                               Resource=resource, Dependency=dep, Source_File=source,
                               Source_Line=op.line if op is not None else "", Evidence_Level=level,
                               Instruction_PC=op.pc if op is not None else "",
                               Contract_Source=evidence, Details=detail))
            if op is not None:
                marked[(hart, op.line)] = event_id
            return event_id

        acquire = []
        dma = list(dma_events(harts[1]))
        end_to_end_dma = []
        launch_id = ""
        for hart, instructions in enumerate(harts):
            prev_id = ""
            for op in instructions:
                kind = ""
                resource = ""
                contract = ""
                detail = op.operands
                if op.is_barrier:
                    kind, resource = "barrier_csr", "cluster_barrier"
                    contract = "/opt/snax-streamer-gemm/sw/snRuntime/src/sync.h:65"
                elif hart == 0 and op.is_write and op.csr in CONFIG:
                    kind, resource = "config_write", "CSR staging"
                    contract = f"{CSR_SOURCE}:10"
                    detail = f"{op.operands}; trace_operand={op.write_value()}"
                elif hart == 0 and op.is_write and op.csr in LAUNCH:
                    kind = "gemm_launch" if op.csr == 0x3DB else "streamer_launch"
                    if op.literal == "0":
                        kind = "await_csr"
                    resource, contract = "accelerator", f"{CSR_SOURCE}:57,73,76"
                elif op.mnemonic in {"dmsrc", "dmdst", "dmstr", "dmrep"}:
                    kind, resource = "dma_setup", "DMA engine"
                elif op.mnemonic.startswith("dmcpy"):
                    kind, resource = "dma_request", "DMA engine"
                    contract = "/opt/snax-streamer-gemm/sw/snRuntime/src/dma.h:57,135"
                elif op.mnemonic == "dmstati":
                    kind, resource = "dma_poll", "DMA engine"
                    contract = "/opt/snax-streamer-gemm/sw/snRuntime/src/dma.h:158"
                if kind:
                    event_id = emit(kind, hart, op, dep=prev_id, resource=resource,
                                    evidence=contract, detail=detail)
                    if prev_id:
                        edges.append(dict(Variant=variant, From=prev_id, To=event_id,
                                          Edge_Type="program_order", Evidence_Level="MEASURED"))
                    prev_id = event_id
                    if kind == "gemm_launch":
                        launch_id = event_id

        for request, first, idle, branch in dma:
            req_id = marked[(1, request.line)]
            idle_id = emit("dma_idle_sample", 1, idle, dep=req_id, resource="DMA engine",
                           evidence="/opt/snax-streamer-gemm/sw/snRuntime/src/dma.h:158",
                           detail=f"next branch line {branch.line} reads t0=0 at cycle {branch.cycle}")
            end_to_end_dma.append((request, first, idle, branch, idle_id))
            edges.append(dict(Variant=variant, From=req_id, To=idle_id,
                              Edge_Type="request_to_observed_idle", Evidence_Level="DERIVED"))
        for index, (left, right) in enumerate(zip(harts[0], harts[0][1:])):
            gap = right.cycle - left.cycle
            if not left.is_barrier or gap <= 100:
                continue
            completing = [d for d in end_to_end_dma if left.cycle <= d[2].cycle <= right.cycle]
            contained = [d for d in completing if left.cycle <= d[0].cycle]
            assert contained
            long_id = emit("barrier_following_gap", 0, left, dep=marked[(0, left.line)],
                           duration=gap, level="DERIVED", resource="synchronization window",
                           detail=f"next hart0 instruction {right.pc} at {right.cycle}")
            resume_id = emit("hart0_next_instruction", 0, right, dep=long_id, resource="host",
                             detail=right.mnemonic)
            edges.append(dict(Variant=variant, From=long_id, To=resume_id,
                              Edge_Type="end_of_observed_gap", Evidence_Level="DERIVED"))
            last = completing[-1]
            peers = [op for op in harts[1] if op.is_barrier and last[2].cycle <= op.cycle <= right.cycle]
            peer = peers[0] if peers else None
            if peer:
                peer_id = marked[(1, peer.line)]
                edges.append(dict(Variant=variant, From=last[4], To=peer_id,
                                  Edge_Type="software_wait_before_barrier", Evidence_Level="DERIVED"))
                edges.append(dict(Variant=variant, From=peer_id, To=resume_id,
                                  Edge_Type="cross_hart_barrier_release_candidate", Evidence_Level="INFERRED"))
            intervals = sum(idle.cycle - req.cycle for req, _, idle, _, _ in contained)
            stages.append(dict(Variant=variant, Gap_Index=len(acquire)+1,
                               Start_Offset=left.cycle-start, End_Offset=right.cycle-start,
                               Gap_Cycles=gap, DMA_Requests=len(contained),
                               DMA_Carry_In=len(completing)-len(contained),
                               DMA_Overlap_Sum=sum(d[2].cycle-max(left.cycle,d[0].cycle) for d in completing),
                               Request_to_Idle_Sum=intervals, Other_In_Gap=gap-intervals,
                               First_Request_Offset=contained[0][0].cycle-start,
                               Last_Idle_Offset=last[2].cycle-start,
                               Hart1_Barrier_Offset=peer.cycle-start if peer else "N/A",
                               Last_Idle_to_Hart0_Next=right.cycle-last[2].cycle))
            acquire.append(gap)

        if launch_id:
            emit("accelerator_completion_signal", None, dep=launch_id, level="UNKNOWN",
                 resource="accelerator", detail="the instruction trace does not expose internal done")
        emit("resource_arbitration", None, level="UNKNOWN", resource="TCDM/CSR/DMA",
             detail="no physical request/grant waveform in this trace")
        assert len(acquire) == 4 and sum(acquire) == expected
        matched = [r for r in stages if r["Variant"] == variant]
        sum_intervals = sum(r["Request_to_Idle_Sum"] for r in matched)
        summary.append(dict(Variant=variant, Window_Cycles=part["cycles"], Barrier_Gaps=sum(acquire),
                            Outside_Gaps=part["cycles"]-sum(acquire), DMA_Sample_Sum=sum_intervals,
                            Inside_Gaps_Other=sum(acquire)-sum_intervals,
                            Requests=sum(r["DMA_Requests"] for r in matched),
                            Carry_In=sum(r["DMA_Carry_In"] for r in matched),
                            Overlapped_Request_to_Idle=sum(r["DMA_Overlap_Sum"] for r in matched),
                            Start_Cycle=start))

    save(report / "data/event_timeline.csv", events)
    save(report / "data/event_dependencies.csv", edges)
    save(report / "data/barrier_gap_breakdown.csv", stages)
    save(report / "data/critical_path_intervals.csv", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("accepted", type=Path)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    diagnose(args.accepted, args.report)
