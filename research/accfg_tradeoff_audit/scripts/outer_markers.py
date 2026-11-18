"""Add a shared outer window only for the separate envelope replay."""
from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text()
start="    _mlir_ciface_streamer_matmul(&memrefA, &memrefB, &memrefC);"
end="    int nerr = 0;"
assert s.count(start)==s.count(end)==1
s=s.replace(start,'    uint32_t audit_start, audit_end;\n'
                  '    asm volatile("csrr %0, mcycle" : "=r"(audit_start) :: "memory");\n'+start)
sentinel="    snrt_cluster_hw_barrier();"
s=s.replace(sentinel,sentinel+'\n'
                  '    asm volatile("csrr %0, mcycle" : "=r"(audit_end) :: "memory");',1)
s=s.replace(end,'    printf("AUDIT_OUTER start=%u end=%u cycles=%u\\n", audit_start, audit_end, audit_end-audit_start);\n'+end)
p.write_text(s)
