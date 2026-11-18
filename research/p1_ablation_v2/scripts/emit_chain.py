"""Emit explicitly scheduled accfg IR and independently calculate golden tensors."""
import argparse
from pathlib import Path


def setup(dest, prior, fields):
    operands = ", ".join(f'"{key}_ptr" = %{value} : i32' for key,value in fields)
    return f'    %{dest} = accfg.setup "snax_gemm" from %{prior} to ({operands}) : !accfg.state<"snax_gemm">'


def emit_ir(case, method, template):
    if case in (2,3) and method != "s":
        raise ValueError("Legal policy refuses early movement for all-late or state-observing calls")
    early = []
    late = []
    call = "    %a1 = func.call @materialize(%c0) : (i32) -> i32"
    early_fields = (("b","b1"),("c","c1"))
    if case == 1:
        # Independent second GEMM; every field is available before first await.
        (early if method == "g" else late).append(
            setup("after","before",(("a","a_alt"),*early_fields)))
    elif case == 2:
        late.extend((call, "    %is_alt = arith.cmpi eq, %a1, %a_alt : i32",
                     "    %bx = arith.select %is_alt, %b_alt, %b1 : i32",
                     "    %cx = arith.select %is_alt, %c_alt, %c1 : i32",
                     setup("after","before",(("a","a1"),("b","bx"),("c","cx")))))
    elif method == "g":
        early.append(setup("half","before",early_fields))
        late.extend((call, setup("after","half",(("a","a1"),))))
    else:
        late.extend((call,setup("after","before",(("a","a1"),*early_fields))))
    return template.replace("@EARLY@","\n".join(early)).replace("@LATE@","\n".join(late))


def values(k, seed):
    matrices = []
    for _ in range(5):
        matrix = []
        for _ in range(8):
            row = []
            for _ in range(k):
                seed ^= (seed << 13) & 0xffffffff
                seed ^= seed >> 17
                seed ^= (seed << 5) & 0xffffffff
                row.append(seed % 15 - 7)
            matrix.append(row)
        matrices.append(matrix)
    return matrices


def product(a,b):
    return [[sum(x*y for x,y in zip(row,col,strict=True)) for col in b] for row in a]


def expected(k, seed, case):
    a0,a1,b0,b1,b2 = values(k,seed)
    first = product(a0,b0)
    q = [[max(-128,min(127,int(x/3))) for x in row] for row in first]
    padded = [row + [0]*(k-8) for row in q]
    b = b2 if case == 2 and first[0][0] & 1 else b1
    def init(name, ctype, array):
        fmt = ", ".join(str(x) for row in array for x in row)
        return f"static const {ctype} {name}[64] = {{{fmt}}};"
    return "\n".join((init("expected_first","int32_t",first),
                      init("expected_packed","int8_t",q),
                      init("expected_second","int32_t",product(a1 if case == 1 else padded,b))))+"\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("template",type=Path)
    ap.add_argument("ir",type=Path)
    ap.add_argument("gold",type=Path)
    ap.add_argument("k",type=int)
    ap.add_argument("seed",type=int)
    ap.add_argument("case",type=int,choices=range(4))
    ap.add_argument("method",choices=("s","g"))
    args = ap.parse_args()
    args.ir.write_text(emit_ir(args.case,args.method,args.template.read_text()))
    args.gold.write_text(expected(args.k,args.seed,args.case))
