"""Retain native pipeline slices and time pinned xDSL pass calls out of I/O."""
import io
import json
from pathlib import Path
import resource
import shlex
import subprocess
import sys
import time

from compiler.tools.snax_opt_main import SNAXOptMain
from compiler.transforms.accfg_config_overlap import AccfgConfigOverlapPass
from compiler.transforms.accfg_dedup import AccfgDeduplicate
from compiler.transforms.convert_accfg_to_csr import ConvertAccfgToCsrPass
from compiler.transforms.convert_linalg_to_accfg import (
    ConvertLinalgToAcceleratorPattern, ConvertSnaxStreamToAcceleratorPattern, TraceStatesPass)
from xdsl.parser import Parser
from xdsl.pattern_rewriter import PatternRewriteWalker
from xdsl.printer import Printer

job=Path(sys.argv[1])
flags=sys.argv[2:]
method=flags[0].split("=")[0]
# Use Make's own expansion, including NO_CHECK and exact side-effect passes.
dry=subprocess.check_output(["make","-n","-W","generated.preprocfinal.mlir",
    "generated.stream.snax-opt.mlir",*flags],text=True)
line=next(line for line in dry.splitlines() if "/snax-opt -p " in line)
(job/"pass_expanded_command.txt").write_text(line+"\n")
prefix,tail=line.split("convert-linalg-to-accfg,",1)
prefix=prefix.rstrip(",")
cmd=shlex.split(prefix)
# Prefix has no spaces inside a pipeline option.
subprocess.run([*cmd,"generated.preprocfinal.mlir","-o",str(job/"before_accfg.mlir")],check=True)
opt=tail.split(",accfg-",1)[0].split(",convert-accfg-to-csr",1)[0]
# The canonicalization expression quotes its comma-separated arguments.
subprocess.run([*shlex.split(prefix+','+"convert-linalg-to-accfg,"+opt),
    "generated.preprocfinal.mlir","-o",str(job/"preopt.mlir")],check=True)

def snapshot(op):
    buffer=io.StringIO()
    Printer(stream=buffer).print_op(op)
    return len(list(op.walk())),len(buffer.getvalue().encode())

def run_one(rep):
    samples=[]
    def measured(name,apply,op=None):
        prior=snapshot(op) if op is not None else (None,None)
        t=time.perf_counter_ns()
        val=apply()
        elapsed=time.perf_counter_ns()-t
        after=snapshot(op if op is not None else val)
        samples.append(dict(Rep=rep,Stage=name,Milliseconds=elapsed/1e6,
                    Ops_Before=prior[0],Ops_After=after[0],IR_Bytes_Before=prior[1],IR_Bytes_After=after[1],
                    Process_Peak_RSS_KiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss))
        return val
    ctx=SNAXOptMain(args=[]).ctx
    before_text=(job/"before_accfg.mlir").read_text()
    native_text=(job/"preopt.mlir").read_text()
    before=measured("parse_pre_accfg",lambda:Parser(ctx,before_text).parse_module())
    def convert():
        PatternRewriteWalker(ConvertLinalgToAcceleratorPattern(before)).rewrite_module(before)
        PatternRewriteWalker(ConvertSnaxStreamToAcceleratorPattern(before)).rewrite_module(before)
    measured("construct_accfg",convert,before)
    measured("trace_states",lambda:TraceStatesPass().apply(ctx,before),before)
    op=measured("parse_preopt",lambda:Parser(ctx,native_text).parse_module())
    if method in {"DEDUP_ONLY","ACCFG_BOTH"}:
        measured("accfg_dedup",lambda:AccfgDeduplicate().apply(ctx,op),op)
    if method in {"OVERLAP_ONLY","ACCFG_BOTH"}:
        measured("accfg_overlap",lambda:AccfgConfigOverlapPass().apply(ctx,op),op)
    measured("accfg_to_csr",lambda:ConvertAccfgToCsrPass().apply(ctx,op),op)
    # Validate the manually timed pass slices against the regular Make build.
    if rep==0:
        official=Parser(ctx,(job/"generated.stream.snax-opt.mlir").read_text()).parse_module()
        assert op.is_structurally_equivalent(official),"timed slices differ from native output"
        op.verify()
    return samples

results=[row for rep in range(9) for row in run_one(rep)]
(job/"passes.json").write_text(json.dumps(results,indent=2)+"\n")
