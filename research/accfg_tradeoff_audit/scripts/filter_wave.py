"""Stream only the selected signal transitions out of a Verilated VCD FIFO."""
import csv
import sys
from collections import defaultdict

output = csv.writer(sys.stdout)
output.writerow(["VCD_Tick", "Signal", "Value", "Hierarchy"])
aliases = defaultdict(list)
scope = []
top = "i_snax_core_0_acc_0_snax_streamer_gemm"
for line in sys.stdin:
    columns = line.split()
    if not columns:
        continue
    token = columns[0]
    if token == "$enddefinitions":
        break
    if token == "$scope":
        scope.append(columns[2])
    elif token == "$upscope":
        scope.pop()
    elif token == "$var":
        code, name = columns[3:5]
        short = None
        if name == "cycle_q" and "gen_core[0]" in scope:
            short = "hart0_mcycle"
        elif name == "dma_busy_o" and scope[-1] == "i_axi_dma_tc_snitch_fe":
            short = "hart1_dma_busy"
        elif scope[-1] == "i_cluster" and name == "barrier_out":
            short = "cluster_barrier_out"
        elif scope[-1] == "BareBlockGemm_i" and name == "io_busy_o":
            short = "gemm_busy"
        elif scope[-1] == "streamer" and name in {"io_busy_o", "io_csr_valid", "io_csr_ready"}:
            short = "streamer_" + name.removeprefix("io_")
        elif scope[-1] == "csr_manager" and "i_snax_streamer_gemm_streamer_top" in scope:
            if name in {"io_csr_config_out_bits_18", "io_csr_config_out_bits_19", "io_csr_config_out_bits_20"}:
                short = "stage_" + ("A", "B", "C")[int(name.rsplit("_", 1)[1]) - 18]
        elif scope[-1] == top and name == "acc_csr_reg_set_valid":
            short = "gemm_config_valid"
        if short:
            aliases[code].append((short, ".".join((*scope, name))))

names = {label for group in aliases.values() for label, _ in group}
assert {"hart0_mcycle", "gemm_busy", "streamer_busy_o", "hart1_dma_busy", "stage_A", "stage_B", "stage_C"} <= names
tick = 0
for line in sys.stdin:
    lead = line[0]
    if lead == "#":
        tick = int(line[1:])
        continue
    if lead == "b":
        value, sep, tail = line[1:].partition(" ")
        if not sep:
            continue
        code = tail.strip()
    elif lead in "01xXzZ":
        value, code = lead, line[1:].strip()
    else:
        continue
    if code in aliases:
        for label, path in aliases[code]:
            output.writerow([tick, label, value, path])
