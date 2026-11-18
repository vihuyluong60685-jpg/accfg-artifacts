"""Read-only small-block feasibility probe using the pinned xDSL dialect."""
import argparse
import json
from pathlib import Path

from compiler.dialects import accfg
from compiler.tools.snax_opt_main import SNAXOptMain
from xdsl.dialects import func
from xdsl.ir import Block
from xdsl.parser import Parser

SUPPORTED = {"a_ptr","b_ptr","c_ptr"}


def analyze(path, audited_call):
    module = Parser(SNAXOptMain(args=[]).ctx,path.read_text()).parse_module()
    module.verify()
    previous,setup = [op for op in module.walk() if isinstance(op,accfg.SetupOp)]
    uses = [entry.operation for entry in previous.out_state.uses]
    launches = [op for op in uses if isinstance(op,accfg.LaunchOp)]
    assert len(uses)==2 and setup in uses and len(launches)==1
    launch, = launches
    block = setup.parent_block()
    assert block is launch.parent_block() and setup.accelerator.data=="snax_gemm"
    ordered = list(block.ops)
    points = {op:i for i,op in enumerate(ordered)}
    assert len({use.operation for use in setup.out_state.uses})==1
    names = dict(setup.iter_params())
    assert set(names)==SUPPORTED
    ready = []
    late = []
    for name, operand in names.items():
        owner = operand.owner
        if owner is block or (not isinstance(owner,Block) and owner in points and points[owner]<points[launch]):
            ready.append(name)
        else:
            late.append(name)
    intervening = ordered[points[launch]+1:points[setup]]
    unknown = []
    for op in intervening:
        if isinstance(op,accfg.AwaitOp) and op.token is launch.token:
            continue
        if op.name in {"arith.cmpi","arith.select"}:
            continue
        if isinstance(op,func.CallOp) and op.callee.root_reference.data==audited_call:
            continue
        unknown.append(op.name)
    action = "retain-serial" if unknown or not ready else ("whole" if not late else "partial")
    return dict(Input=str(path),Audited_No_Staging_Effect=audited_call,
                Early_Operands=ready,Late_Operands=late,Unproven_Intervening_Ops=unknown,
                Action=action,IR_Roles="two uses of previous state, same block, one subsequent state user",
                Assumptions="single owner; independent pointer CSRs; launch capture; audited memory and handoff preserved")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ir",type=Path)
    parser.add_argument("--audited-call")
    opts=parser.parse_args()
    print(json.dumps(analyze(opts.ir,opts.audited_call)))
