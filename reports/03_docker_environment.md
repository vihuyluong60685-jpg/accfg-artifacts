# 03 官方 Docker 环境验收

2026-11-17。**PASS**：官方镜像成功拉取，原始 `/repo/hello-world.sh` 退出 0，打印
`If you see this, all is well!`。未修改 hello-world.sh，无需 PEP 668 补丁。

## 不可变镜像

- 原始引用：`ghcr.io/kuleuven-micas/accfg-artifacts:latest`。
- 本次 digest/image ID：`sha256:a3dd42b69696b63e3c83a1a1719c0b2ae1965673d60251c468b337b3bf9ad813`。
- 实验引用：`ghcr.io/kuleuven-micas/accfg-artifacts@sha256:a3dd42b69696b63e3c83a1a1719c0b2ae1965673d60251c468b337b3bf9ad813`。
- 本地记录大小：11854097849 字节；清单压缩层合计 3049657330 字节。
- 平台：linux/amd64；镜像创建时间：2025-07-10T08:02:30.930658211Z。
- 拉取开始：2026-11-17T05:33:42.322232+00:00；结束：2026-11-17T05:48:49.065142+00:00；耗时 906.7 秒，退出 0。
- 未下载或导入另一个容器镜像归档；未使用第三方镜像。

## 容器与工具

保留容器 `accfg-repro-20261117`，从上述 digest 创建。项目 bind mount 到 `/repo`，
工作目录 `/repo`，使用非交互 Docker exec，无 `-it`。
`mountpoint /repo` 和 OpenGeMM 预编译 Verilator 仿真器存在性检查通过。
环境设置 `PYTHONUNBUFFERED=1`、`MPLBACKEND=Agg`、`MAKEFLAGS=-l2`。
最后一项限制 Make 的负载并发，避免作者 `make -j` 无界并发；未改变编译选项或论文算法。
容器运行作者默认 root 用户；Docker 客户端由普通 WSL 用户经既有 docker 组访问。

- Python：3.10.14。
- xDSL：0.22.0+12.g791e89d8；pip 直接来源提交：`791e89d87cc23303e9ce3ac2d7e48e25eecc0e03`。
- snax-opt：来自挂载的论文目标 snax-mlir 源码。
- MLIR/Clang：17.0.6。
- Spike：`/riscv/bin/spike`，作者基础脚本已找到；实际模拟另见 05 报告。
- Verilator：5.026，2024-06-15，revision v5.026-43-g065f36ab5。
- RISC-V GCC：13.2.0。
- numpy 1.26.4、pandas 2.2.2、matplotlib 3.10.3、seaborn 0.13.2、scipy 1.15.3。

完整安装后版本列表见 `configs/requirements_observed.txt`；镜像与工具链记录见
`configs/official_image.json`、`configs/official_registry_manifest.json` 和 `configs/toolchain_versions.json`。
所有 pip 安装只发生在该实验容器中，未改动宿主 Python、Conda 或 Windows 软件。

## 日志与限制

- hello-world：`reports/logs/20261117T054915Z_official-hello-world_d4a43a/`，退出 0。
- 镜像拉取：`reports/logs/20261117T053342Z_official-image-pull_800dd8/`，退出 0。
- 工具链补充记录：`reports/logs/20261117T055023Z_capture-toolchain-versions_da965e/`，退出 0。
- 额外检查曾错误假设 xDSL Git 源目录为 `/xdsl`，该诊断命令退出 128；
  随后通过 Python 安装位置和 pip 来源信息正确记录。此失败未被计作作者环境脚本失败或实验成功。

本阶段只证明基础环境可执行；不代表 OpenGeMM、Gemmini 或完整入口已通过。

## 镜像内源码补充核验

Spike 帮助页报告 1.1.1-dev；其镜像内源码提交为
`2a0bb5f543974a039ab1ba50b0ac362c6646b74d`。
libgemmini 提交为 `5b1254a7dc72f757442280e7f28ef30542c78533`。
镜像内 snax-mlir 提交为 `0df8b515768232036bceb6af7a6d5935b5e1a3db`，与挂载源码目标一致。
路径和 SHA 见 `configs/image_source_versions.json`。
