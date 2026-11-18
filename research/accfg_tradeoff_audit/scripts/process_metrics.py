"""Measure a fresh command's wall time and maximum Linux child RSS."""
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

out=Path(sys.argv[1])
cmd=sys.argv[2:]
t=time.perf_counter_ns()
rc=subprocess.run(cmd,check=False).returncode
t=time.perf_counter_ns()-t
usage=resource.getrusage(resource.RUSAGE_CHILDREN)
out.write_text(json.dumps(dict(Elapsed_Seconds=t/1e9,Max_Child_RSS_KiB=usage.ru_maxrss,
                                Exit=rc,Command=cmd))+"\n")
raise SystemExit(rc)
