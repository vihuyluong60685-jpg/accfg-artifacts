#!/usr/bin/env python3
"""Run a command, preserving merged output, exit code and source provenance."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}


def main():
    if len(sys.argv) < 4 or sys.argv[2] != "--":
        raise SystemExit("usage: record_command.py LABEL -- COMMAND [ARG ...]")
    label = sys.argv[1]
    if not label.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("LABEL must contain only letters, digits, hyphens or underscores")
    start = datetime.datetime.now(datetime.timezone.utc)
    run_id = start.strftime("%Y%m%dT%H%M%SZ") + "_" + label + "_" + uuid.uuid4().hex[:6]
    directory = ROOT / "reports" / "logs" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    metadata = {
        "run_id": run_id, "command": sys.argv[3:], "cwd": str(Path.cwd()),
        "started_at": start.isoformat(), "code_commit": git("rev-parse", "HEAD")["stdout"].strip(),
        "worktree_status": git("status", "--porcelain=v1"),
        "submodule_status": git("submodule", "status", "--recursive"),
        "status": "RUNNING", "output": str(directory / "output.log"),
    }
    manifest = directory / "metadata.json"
    manifest.write_text(json.dumps(metadata, indent=2) + "\n")
    print("AUDIT " + str(manifest), flush=True)
    code = 127
    try:
        with (directory / "output.log").open("wb") as log:
            process = subprocess.Popen(sys.argv[3:], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                while True:
                    chunk = os.read(process.stdout.fileno(), 16384)
                    if not chunk:
                        break
                    log.write(chunk)
                    log.flush()
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                code = process.wait()
            except KeyboardInterrupt:
                process.terminate()
                code = process.wait()
    except OSError as error:
        metadata["error"] = str(error)
    finally:
        output = directory / "output.log"
        metadata.update({"status": "PASS" if code == 0 else "FAIL", "exit_code": code,
                         "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest() if output.exists() else None})
        manifest.write_text(json.dumps(metadata, indent=2) + "\n")
        print("\nAUDIT_EXIT " + str(code), flush=True)
    return code if code >= 0 else 128 - code


if __name__ == "__main__":
    raise SystemExit(main())
