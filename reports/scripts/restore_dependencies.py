#!/usr/bin/env python3
"""Initialize pinned dependencies, recovering the original RoCC commit from Zenodo."""
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BUNDLE_SHA256 = "df36c801ded194acf10e4f977a987e00f9d765154622dcf1e6f4320c6c42b6c3"
TARGETS = {
    "gemmini-rocc-tests": "4fec505cadacec4c371305b90973fa18758e9ac0",
    "snax-mlir": "0df8b515768232036bceb6af7a6d5935b5e1a3db",
    "gemmini-rocc-tests/riscv-tests": "c84daca8824635b7d896003c78f9c6245997cf7a",
    "gemmini-rocc-tests/riscv-tests/env": "0666378f353599d01fc48562b431b1dd049faab5",
    "gemmini-rocc-tests/rocc-software": "fddb795a0b52e82f8f4ce9ead9b1428440a62ab0",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main():
    bundle = ROOT / "reports/dependencies/rocc-software-fddb795.bundle"
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != BUNDLE_SHA256:
        raise SystemExit("Recovery bundle checksum mismatch")
    # Do not repair dirty/misaligned existing checkouts automatically.
    for path, target in TARGETS.items():
        if (ROOT / path / ".git").exists():
            if git("-C", path, "rev-parse", "HEAD") != target:
                raise SystemExit("Inspect existing version deviation first: " + path)
            if git("-C", path, "status", "--porcelain=v1", "--ignore-submodules=all"):
                raise SystemExit("Preserve existing local changes first: " + path)
    git("submodule", "update", "--init", "gemmini-rocc-tests", "snax-mlir")
    git("-C", "gemmini-rocc-tests", "config", "submodule.rocc-software.url", str(bundle))
    # The sole file transport is the checked, versioned recovery bundle.
    git("-C", "gemmini-rocc-tests", "-c", "protocol.file.allow=always",
        "submodule", "update", "--init", "riscv-tests", "rocc-software")
    git("-C", "gemmini-rocc-tests/riscv-tests", "submodule", "update", "--init", "--recursive")
    for path, target in TARGETS.items():
        if git("-C", path, "rev-parse", "HEAD") != target:
            raise SystemExit("Dependency verification failed: " + path)
        if git("-C", path, "status", "--porcelain=v1"):
            raise SystemExit("Dependency is dirty: " + path)
        print("PASS", path, target)


if __name__ == "__main__":
    main()
