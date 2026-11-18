#!/usr/bin/env bash
set -euo pipefail
got="$(sha256sum /opt/snax-streamer-gemm-rtl/bin/snitch_cluster.vlt | cut -d' ' -f1)"
test "$got" = 39ab1f5e980f8afb7e8f018c5a8678f93c26be96bff717af834c0223af7b29d9
printf 'RTL simulator SHA-256 %s\n' "$got"
sha256sum /opt/gen_trace.py
clang-17 --version
mlir-opt-17 --version
verilator --version
python3 --version
python3 -c 'import importlib.metadata; print("xDSL package", importlib.metadata.version("xdsl"))'
uname -a
