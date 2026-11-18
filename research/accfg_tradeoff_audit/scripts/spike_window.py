"""Classify exactly the two rdcycle instructions in the shared Gemmini harness."""
from collections import Counter
import json
from pathlib import Path
import re
import subprocess
import sys

job=Path(sys.argv[1])
dis=(job/"disassembly.txt").read_text()
main=re.search(r"^[a-f0-9]+ <main>:\n(.*?)(?=^[0-9a-f]+ <|\Z)",dis,re.M|re.S)[1]
markers=[int(x,16) for x in re.findall(r"^\s*([0-9a-f]+):[^\n]*(?:rdcycle|\bcycle\b)",main,re.M)]
assert len(markers)>=2,markers
command=["timeout","150s","spike","-l","--extension=gemmini",str(job/"test.x")]
pattern=re.compile(r"^core\s+\d+:\s+0x([0-9a-f]+)\s+\(0x([0-9a-f]+)\)")
open_window=False
finished=False
n=0
rocc=Counter()
stdout=[]
with (job/"timed_trace.txt").open("w") as window:
    with subprocess.Popen(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT) as process:
        for line in process.stdout:
            match=pattern.match(line)
            if not match:
                stdout.append(line)
                continue
            pc,opcode=(int(field,16) for field in match.groups())
            if pc==markers[1] and open_window:
                finished=True
                open_window=False
            if open_window:
                n+=1
                window.write(line)
                if opcode&127 in {0x0b,0x2b,0x5b,0x7b}:
                    rocc[f"{opcode&127:02x}:{opcode>>25}"]+=1
            if pc==markers[0] and not finished:
                open_window=True
        rc=process.wait()
(job/"stdout.txt").write_text("".join(stdout))
(job/"spike.exit").write_text(f"{rc}\n")
measures=re.findall(r"Cycles taken: (\d+)","".join(stdout))
out=dict(Command=command,Window_PCs=[hex(x) for x in markers[:2]],Spike_Exit=rc,
         Counter_Interval=int(measures[0]) if measures else None,Dynamic_Inside=n,In_Interval_RoCC=sum(rocc.values()),
         RoCC_Opcode_Funct7=dict(rocc),Complete=finished)
(job/"spike.json").write_text(json.dumps(out,indent=2)+"\n")
print(json.dumps(out))
assert finished and measures and int(measures[0])-n in {0,1,2},out
raise SystemExit(rc)
