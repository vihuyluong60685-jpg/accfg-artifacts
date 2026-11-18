"""Generate common accfg dispatch IR and independent graph golden fixtures."""
import argparse
import json
from math import exp
from pathlib import Path
from random import Random

# Order matches the pinned SNAXGEMMAccelerator field map and runtime.
FIELD_VALUES = {
    "loop_bound_0":1,"loop_bound_1":1,"loop_bound_2":1,
    "a_tstride_0":256,"a_tstride_1":0,"a_tstride_2":512,
    "b_tstride_0":256,"b_tstride_1":512,"b_tstride_2":0,
    "c_tstride_0":0,"c_tstride_1":256,"c_tstride_2":256,
    "a_sstride_0":1,"a_sstride_1":8,"b_sstride_0":1,"b_sstride_1":8,
    "c_sstride_0":4,"c_sstride_1":32,
    "a_ptr":None,"b_ptr":None,"c_ptr":None,"K":1,"N":1,"M":1,"subtractions":0,
}
SHAPE = 8
SEEDS = (11,37)
LUT = [round(256*exp(-i/2)) for i in range(32)]


def emit_ir():
    constants = [f"    %v{val} = arith.constant {val} : i32"
                 for val in sorted({x for x in FIELD_VALUES.values() if x is not None})]
    def setup(stage):
        prior = ' from %s0' if stage else ''
        fields = ((name,f"v{value}" if value is not None else f"{name[0]}{stage}")
                  for name,value in FIELD_VALUES.items())
        params = ", ".join(f'"{name}" = %{op} : i32' for name,op in fields)
        return f'    %s{stage} = accfg.setup "snax_gemm"{prior} to ({params}) : !accfg.state<"snax_gemm">'
    def launch(stage):
        return ('    %r{0} = "accfg.launch"(%one, %one, %s{0}) '
                '<{{accelerator = "snax_gemm", param_names = ["launch_streamer", "launch_gemm"]}}>'
                ' : (i5, i5, !accfg.state<"snax_gemm">) -> !accfg.token<"snax_gemm">').format(stage)
    def wait(stage):
        return f'    "accfg.await"(%r{stage}) : (!accfg.token<"snax_gemm">) -> ()'
    return "\n".join([
        'builtin.module {', '  func.func private @publish_middle(i32, i32) -> ()',
        '  func.func @gate_graph(%a0: i32, %b0: i32, %c0: i32, %a1: i32, %b1: i32, %c1: i32) {',
        '    %one = arith.constant 1 : i5', *constants,
        setup(0), launch(0), wait(0),
        '    func.call @publish_middle(%c0, %a1) : (i32, i32) -> ()',
        setup(1), launch(1), wait(1), '    func.return','  }','}', ''
    ])


def sat(value,lo=-128,hi=127):
    return min(hi,max(lo,value))


def trunc(x,divisor):
    return (-1 if x < 0 else 1)*(abs(x)//divisor)


def operate(a,b):
    return [[sum(x*y for x,y in zip(row,weights,strict=True)) for weights in b] for row in a]


def draw(rng,rows,cols,limit):
    return [[rng.randint(-limit,limit) for _ in range(cols)] for _ in range(rows)]


def fixture(graph,seed):
    rng = Random(seed)
    data = draw(rng,8,8,7)
    if graph == "mobile":
        weights_rng = Random(91)
        b0 = draw(weights_rng,8,8,7)
        b1 = draw(weights_rng,8,8,7)
        kernel = draw(weights_rng,9,8,3)
    else:
        b0 = draw(rng,8,8,7)
        values = draw(rng,8,8,7)
        b1 = [list(col) for col in zip(*values,strict=True)]
        kernel = []
    producer = operate(data,b0)
    if graph == "mobile":
        stem = [[sat(trunc(x,4),0,24) for x in px] for px in producer]
        inter = []
        for row in range(2):
            for col in range(4):
                dot = [0]*8
                for dr in (-1,0,1):
                    for dc in (-1,0,1):
                        nr,nc = row+dr,col+dc
                        if 0 <= nr < 2 and 0 <= nc < 4:
                            fs = kernel[(dr+1)*3+dc+1]
                            dot = [a+b*c for a,b,c in zip(dot,stem[nr*4+nc],fs,strict=True)]
                inter.append([sat(trunc(x,8),0,24) for x in dot])
    else:
        inter = []
        for row in producer:
            xmax = max(row)
            weights = [LUT[min(31,(xmax-x+4)//8)] for x in row]
            denom = sum(weights)
            inter.append([(weight*127+denom//2)//denom for weight in weights])
    consumer = operate(inter,b1)
    if graph == "mobile":
        final = [[sat(trunc(x,8)+r) for x,r in zip(row,inp,strict=True)] for row,inp in zip(consumer,data,strict=True)]
    else:
        final = [[sat(trunc(x,127)) for x in row] for row in consumer]
    assert any(any(row) for row in final) and len({tuple(row) for row in final})>1
    return {"seed":seed,"data":data,"b0":b0,"b1":b1,"kernel":kernel,
            "producer":producer,"inter":inter,"consumer":consumer,"final":final}


def emit_header(graph,path,cases):
    def flat(rows):
        return ', '.join(str(x) for row in rows for x in row)
    parts = ["/* generated independent Python graph semantics */"]
    for key in ("data","b0","b1","producer","inter","consumer","final"):
        ty = "int32_t" if key in {"producer","consumer"} else "int8_t"
        values = ",\n".join("    {"+flat(case[key])+"}" for case in cases)
        parts.append(f"static const {ty} fixture_{key}[{len(cases)}][64] = {{\n{values}\n}};")
    if graph=="mobile":
        parts.append(f"static const int8_t fixture_kernel[72] = {{{flat(cases[0]['kernel'])}}};")
    else:
        parts.append(f"static const int16_t fixture_exp[32] = {{{', '.join(map(str,LUT))}}};")
    parts.append(f"static const unsigned seeds[{len(cases)}] = {{{', '.join(map(str,SEEDS))}}};")
    path.write_text("\n".join(parts)+"\n")


if __name__=="__main__":
    p = argparse.ArgumentParser()
    p.add_argument("graph",choices=("mobile","attention"))
    p.add_argument("ir",type=Path)
    p.add_argument("header",type=Path)
    p.add_argument("reference",type=Path)
    args = p.parse_args()
    cases = [fixture(args.graph,seed) for seed in SEEDS]
    args.ir.write_text(emit_ir())
    emit_header(args.graph,args.header,cases)
    args.reference.write_text(json.dumps({"graph":args.graph,"cases":cases},separators=(",",":"))+"\n")
