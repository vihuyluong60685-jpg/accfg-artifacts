# Git 与环境

研究分支 **research/p1-criticalpath-pilot** 来自已同步的 **cbf660f1cc73dfffd589541c9c382b346a7206fd**。paper-original 为 **ce1567e40962037cda59a236bea6e3458caeb63a**。gh auth status 和 gh api user 确认登录 vihuyluong60685-jpg。origin 是个人 fork，upstream 是作者仓库且 push URL 已禁用。初始化和实验代码分别提交 49f59f8 和 01e8266。

原 checkout 保留在 repro/accfg-2026。备份其中唯一的未跟踪研究目录后创建独立 worktree /home/yanmo/research/projects/accfg-p1-pilot。五个本地子模块对象全部按目标 SHA 成功 git archive。新 worktree 用原 checkout 的本地对象导出 pinned 编译器到隔离目录，历史数据和脚本以只读挂载使用。没有依赖重新下载或改 gitlink。

| 项目 | 实际版本 |
|---|---|
| 主机 | Intel Core i9-13900HX，Windows 11 / WSL2 Ubuntu 22.04，内存约 8 GiB，swap 4 GiB |
| Docker | Desktop client/server 29.9.3；官方镜像 SHA a3dd42b69696b63e3c83a1a1719c0b2ae1965673d60251c468b337b3bf9ad813 |
| OpenGeMM | 预编 snitch_cluster.vlt，SHA 39ab1f5e980f8afb7e8f018c5a8678f93c26be96bff717af834c0223af7b29d9，Verilator 5.026 v5.026-43-g065f36ab5 |
| 编译 | MLIR/Clang 17.0.6，xDSL 791e89d87cc23303e9ce3ac2d7e48e25eecc0e03 |
| 固定环境中未用于 P1 实测 | RISC-V GCC 13.2.0；Spike 1.1.1-dev；libgemmini 5b1254a7dc72f757442280e7f28ef30542c78533 |
| SNAX MLIR | 0df8b515768232036bceb6af7a6d5935b5e1a3db |
| Gemmini tests | 4fec505cadacec4c371305b90973fa18758e9ac0 |
| riscv-tests | c84daca8824635b7d896003c78f9c6245997cf7a |
| riscv-tests/env | 0666378f353599d01fc48562b431b1dd049faab5 |
| rocc-software | fddb795a0b52e82f8f4ce9ead9b1428440a62ab0 |

原 run-all 对应 3958aeb14e48a917a1e43ebbb87290becd3cf110，opcode 分类对应 8a306b829af5d9474ba200c4e385343b554cfb81。原数据、图表、配置和日志哈希已复核。试验用 make -j1、3 GiB 容器上限；VCD 用 2 GiB 容器和 FIFO，未全量写盘。[固定版本与备份哈希](../../research/p1_criticalpath_pilot/configs/frozen_baseline.json)
