#!/usr/bin/env python3
"""Ignore only inspected, generated submodule outputs in local Git metadata."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
RULES = {
    "snax-mlir": ["/kernels/streamer_matmul/results/", "/kernels/streamer_matmul/generated.transform.mlir"],
    "gemmini-rocc-tests": ["/bareMetalMLIR/tiled_matmul_*.opt.acc_dialect.x"],
}
for repository, rules in RULES.items():
    location = ROOT / repository
    for rule in rules:
        tracked = subprocess.check_output(["git", "ls-files", "--", rule.lstrip("/")], cwd=location, text=True)
        if tracked:
            raise SystemExit("Rule intersects tracked files; inspect first: " + rule)
    path = Path(subprocess.check_output(["git", "rev-parse", "--git-path", "info/exclude"], cwd=location, text=True).strip())
    if not path.is_absolute():
        path = location / path
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.exists() else ""
    additions = [rule for rule in rules if rule not in existing.splitlines()]
    if additions:
        with path.open("a") as stream:
            stream.write("\n# Local outputs of audited paper reproduction\n" + "\n".join(additions) + "\n")
    print(repository, "local exclude rules verified:", rules)
