"""Scale copies of the same real loop/branch body; track live Python allocations."""
import json
from pathlib import Path
import resource
import sys
import time
import tracemalloc

from compiler.tools.snax_opt_main import SNAXOptMain
from compiler.transforms.accfg_config_overlap import AccfgConfigOverlapPass
from compiler.transforms.accfg_dedup import AccfgDeduplicate
from xdsl.dialects import builtin,func
from xdsl.parser import Parser

source=Path(sys.argv[1])
copies=int(sys.argv[2])
mode=sys.argv[3]
ctx=SNAXOptMain(args=[]).ctx
tracemalloc.start()
op=Parser(ctx,source.read_text()).parse_module()
candidates=[f for f in op.walk() if isinstance(f,func.FuncOp)
            and f.sym_name.data.startswith("streamer_matmul") and f.body.blocks]
assert candidates
for i in range(1,copies):
    for candidate in candidates:
        duplicate=candidate.clone()
        duplicate.properties["sym_name"]=builtin.StringAttr(f"audit_copy_{i}_{candidate.sym_name.data}")
        op.body.block.add_op(duplicate)
op.verify()
before_ops=list(op.walk())
before=tracemalloc.get_traced_memory()[0]
tracemalloc.reset_peak()
t=time.perf_counter_ns()
if mode=="D":
    AccfgDeduplicate().apply(ctx,op)
    AccfgConfigOverlapPass().apply(ctx,op)
elapsed=time.perf_counter_ns()-t
current,peak=tracemalloc.get_traced_memory()
after=len(list(op.walk()))
op.verify()
print(json.dumps(dict(Copies=copies,Mode=mode,Ops_Before=len(before_ops),Ops_After=after,
                     Branches=sum(i.name=="scf.if" for i in before_ops),Loops=sum(i.name=="scf.for" for i in before_ops),
                     Peak_Python_Bytes=peak,Current_Before_Python_Bytes=before,Current_After_Python_Bytes=current,
                     Process_Peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     Tracemalloc_Instrumented_Elapsed_MS=elapsed/1e6)))
