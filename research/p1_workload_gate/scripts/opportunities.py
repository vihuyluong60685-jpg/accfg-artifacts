"""Read-only diagnostics on checked ACCFG SSA, including policy provenance."""
import argparse
import json
from pathlib import Path

from compiler.dialects import accfg
from compiler.inference.scoped_setups import get_scoped_setup_inputs
from compiler.tools.snax_opt_main import SNAXOptMain
from xdsl.dialects import func
from xdsl.ir import Block
from xdsl.parser import Parser

POINTERS={"a_ptr":978,"b_ptr":979,"c_ptr":980}


def parse(path):
    ir=Parser(SNAXOptMain(args=[]).ctx,path.read_text()).parse_module()
    ir.verify()
    return ir


def launches(ir):
    return [op for op in ir.walk() if isinstance(op,accfg.LaunchOp)]


def audit(name,base,dedup,both,contract=None):
    b,d,c=(parse(p) for p in (base,dedup,both))
    roots=[launches(ir) for ir in (b,d,c)]
    assert all(len(v)==2 for v in roots), name
    initial,src = roots[1]
    old_setup=initial.state.owner
    candidate=src.state.owner
    scope=initial.parent_block()
    assert isinstance(old_setup,accfg.SetupOp) and isinstance(candidate,accfg.SetupOp)
    assert candidate.in_state is old_setup.out_state and candidate.parent_block() is scope
    positions={op:i for i,op in enumerate(scope.ops)}
    join=next(u.operation for u in initial.token.uses)
    a=positions[initial]
    fields=[]
    for key,ssa in candidate.iter_params():
        origin=ssa.owner
        ready=origin is scope or (not isinstance(origin,Block) and origin in positions and positions[origin]<a)
        fields.append(dict(Field=key,CSR=POINTERS.get(key),Available_From="block entry" if origin is scope else origin.name,
                           SSA_Position=-1 if origin is scope else positions.get(origin),
                           Ready_At_Launch=ready,Atomic_Group=key if key in POINTERS else "unverified",
                           Independent_Target_Scope=key in POINTERS))
    late=[v["Field"] for v in fields if not v["Ready_At_Launch"]]
    barriers=[]
    for op in scope.ops:
        if not a<positions[op]<positions[candidate] or op is join or op.name in {"arith.select","arith.cmpi"}:
            continue
        callee=op.callee.root_reference.data if isinstance(op,func.Call) else None
        audit_effect="audited memory-only; preserve execution order" if callee and callee==contract else "unknown/observable; block motion"
        barriers.append(dict(Operation=op.name,Callee=callee,Position=positions[op],Effect=audit_effect,Blocked=callee!=contract or not callee))
    allowed=not any(v["Blocked"] for v in barriers)
    for field in fields:
        field["Safe_To_Move"]=bool(allowed and field["Ready_At_Launch"] and field["Independent_Target_Scope"])
    ready=[v["Field"] for v in fields if v["Safe_To_Move"]]
    before,after=roots[2]
    both_setup=after.state.owner
    both_positions={op:i for i,op in enumerate(before.parent_block().ops)}
    first_await=next(u.operation for u in before.token.uses)
    entire_moved=isinstance(both_setup,accfg.SetupOp) and both_positions[both_setup]<both_positions[first_await]
    moved_fields=[v[0] for v in both_setup.iter_params()] if entire_moved else []
    diagnostic=get_scoped_setup_inputs(candidate,scope)
    uses={u.operation for u in old_setup.out_state.uses}
    reason=("whole setup placed before await" if entire_moved else
            "effectful or unsupported setup operand use-def chain" if diagnostic is None else
            "block/state use constraints" if uses!={initial,candidate} else "no observed whole motion")
    original=roots[0][1].state.owner
    assert isinstance(original,accfg.SetupOp)
    original_fields=dict(original.iter_params())
    removed=sorted(set(original_fields)-{v["Field"] for v in fields})
    return dict(Graph=name,Input=str(dedup),Contract=contract,Fields_Before_Dedup=len(original_fields),
                Deduplicated_Fields=removed,
                First_Setup_Fields=len(list(roots[0][0].state.owner.iter_params())),
                Effective_Fields=len(fields),Fields=fields,Late_Fields=late,Safe_Early_Fields=ready,
                Stable_State_Capture_CSR="0x3d5 streamer trigger; GEMM capture 0x3db",
                Capture_Protocol="single owner and independently staged pointer fields only; VCD checked separately",
                First_Launch_SSA_Index=a,First_Await_SSA_Index=positions[join],
                Intervening_Effects=barriers,Both_Moved=moved_fields,Both_Observation=reason,
                Strict_Partial_Opportunity=bool(ready and late),Missed_Safe_Fields=sorted(set(ready)-set(moved_fields)))


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("name")
    for alias in ("base","dedup","both"):
        p.add_argument(alias,type=Path)
    p.add_argument("--audited")
    opts=p.parse_args()
    print(json.dumps(audit(opts.name,opts.base,opts.dedup,opts.both,opts.audited)))
