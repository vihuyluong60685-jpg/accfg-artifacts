"""Independent packed-input golden values, generated on the host before simulation."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("k", type=int)
parser.add_argument("seed", type=int)
parser.add_argument("output", type=Path)
args = parser.parse_args()

state = args.seed


def element():
    global state
    state ^= (state << 13) & 0xFFFFFFFF
    state ^= state >> 17
    state ^= (state << 5) & 0xFFFFFFFF
    return state % 15 - 7


def matrix():
    return [[element() for _ in range(args.k)] for _ in range(8)]


def gemm(a, bt):
    return [sum(x*y for x,y in zip(row,col,strict=True)) for row in a for col in bt]


a0, a1, b0, b1, b2 = (matrix() for _ in range(5))
first = gemm(a0,b0)
second = gemm(a1,b2 if first[0]&1 else b1)
with args.output.open("w") as stream:
    for name, values in [("pilot_first_gold",first),("pilot_second_gold",second)]:
        stream.write(f"static const int32_t {name}[64] = {{ {', '.join(map(str, values))} }};\n")
