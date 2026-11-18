"""Construct one hand-written accfg schedule; each target write stays unique."""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("method", choices=["S", "W", "G"])
parser.add_argument("template", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()

state = '!accfg.state<"snax_gemm">'
early = ""
late = f'    %after = accfg.setup "snax_gemm" from %before to ("a_ptr" = %a1 : i32, "b_ptr" = %b1 : i32, "c_ptr" = %c1 : i32) : {state}'
if args.method == "G":
    early = f'    %early = accfg.setup "snax_gemm" from %before to ("a_ptr" = %a1 : i32, "c_ptr" = %c1 : i32) : {state}'
    late = f'    %after = accfg.setup "snax_gemm" from %early to ("b_ptr" = %b1 : i32) : {state}'
args.output.write_text(args.template.read_text().replace("@EARLY@", early).replace("@LATE@", late))
