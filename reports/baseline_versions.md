# 论文基线与本地版本记录

检查日期：2026-11-17（Asia/Shanghai）。本次只管理 Git，未运行论文实验或容器。

## 主仓库

- 原作者仓库：<https://github.com/KULeuven-MICAS/accfg-artifacts.git>
- 用户确认的 Fork：<https://github.com/vihuyluong60685-jpg/accfg-artifacts.git>
- GitHub API 已确认 Fork 的 `parent.full_name` 为 `KULeuven-MICAS/accfg-artifacts`。
- 原始提交：`ce1567e40962037cda59a236bea6e3458caeb63a`。
- 初始化前 HEAD、原始本地 `main` 均为上述提交。
- 本地轻量标签 `paper-original` 固定在上述提交；不得移动或覆盖。
- 复现分支 `repro/accfg-2026` 直接从上述提交创建，后续管理提交不改变该基线。
- 标签只固定主仓库及其 gitlink；不代表所有嵌套依赖已成功获取、检出或验证。

## 子模块目标与实际状态

目标 SHA 来自论文主仓库提交及其逐层固定的子模块 Git 树，未使用远程最新分支代替。

| 路径 | 论文基线目标 SHA | 初始化时实际 HEAD | 状态 |
| --- | --- | --- | --- |
| `gemmini-rocc-tests` | `4fec505cadacec4c371305b90973fa18758e9ac0` | `4fec505cadacec4c371305b90973fa18758e9ac0` | HEAD 一致，因嵌套依赖异常而脏 |
| `snax-mlir` | `0df8b515768232036bceb6af7a6d5935b5e1a3db` | `0df8b515768232036bceb6af7a6d5935b5e1a3db` | HEAD 一致，工作树干净 |
| `gemmini-rocc-tests/riscv-tests` | `c84daca8824635b7d896003c78f9c6245997cf7a` | `3df703cd52d5f0d8224e3c50bf03c6cb70efff98` | 版本偏差，索引文件缺失，状态显示 1,425 项 `D ` |
| `gemmini-rocc-tests/rocc-software` | `fddb795a0b52e82f8f4ce9ead9b1428440a62ab0` | 无 | 未初始化；目录为空，无 `.git` 标记及本地对象库 |
| `gemmini-rocc-tests/riscv-tests/env` | `0666378f353599d01fc48562b431b1dd049faab5` | 无 | 论文目标树含该 gitlink；当前目录不存在，未初始化 |

`riscv-tests` 当前偏离版本的树指向 `env` 的
`6de71edb142be36319e380ce782c3d1830c65d68`，这不是论文基线目标。
由于该工作树缺少索引及 `.gitmodules` 文件，顶层 `git submodule status --recursive`
未显示 `env`，因此另从已存在的目标提交对象读取其版本。
`snax-mlir` 的目标树没有嵌套 gitlink。`rocc-software` 目标对象本地不可用，
其内部是否还有嵌套依赖为 **NOT TESTED**，不宣称已穷尽不可用对象中的依赖。

子模块原始 URL（来自各级目标提交的 `.gitmodules`）：

- `gemmini-rocc-tests`：<https://github.com/KULeuven-MICAS/gemmini-rocc-tests/>
- `snax-mlir`：<https://github.com/kuleuven-micas/snax-mlir>
- `riscv-tests`：<https://github.com/riscv/riscv-tests.git>
- `rocc-software`：<https://github.com/ibm/rocc-software>
- `env`：<https://github.com/riscv/riscv-test-env.git>

原始递归状态输出（本次保留，不是完整干净基线）：

```text
 4fec505cadacec4c371305b90973fa18758e9ac0 gemmini-rocc-tests (heads/dev)
+3df703cd52d5f0d8224e3c50bf03c6cb70efff98 gemmini-rocc-tests/riscv-tests (heads/master)
-fddb795a0b52e82f8f4ce9ead9b1428440a62ab0 gemmini-rocc-tests/rocc-software
 0df8b515768232036bceb6af7a6d5935b5e1a3db snax-mlir (remotes/origin/accfg-paper-experiments)
```

空格表示当前 HEAD 与父仓库记录相同；`+` 表示偏差；`-` 表示未初始化。
HEAD 相同仍须检查工作树和嵌套依赖。上述异常全部保留，不暂存 gitlink，
不进行子模块 update、checkout、reset 或修复。

## Docker 版本记录方式

原始 `run-all.sh` 使用 `ghcr.io/kuleuven-micas/accfg-artifacts:latest`；
原始 `Containerfile` 的基础镜像为 `ghcr.io/kuleuven-micas/snax:v0.1.6`。
这里只静态读取文件；镜像是否可用、实际 ID、digest、构建兼容性均为 **NOT TESTED**。

未来每次实验记录镜像引用、平台、不可变的 registry digest、实际 image ID、
构建所用 Git commit 与构建命令。仅记录 `latest` 不足以固定环境。
在已准备好的环境中，可读取 `docker image inspect <镜像引用>` 的
`Id`、`RepoDigests`、`Os`、`Architecture`；若为本地构建且无 RepoDigest，
记录 image ID、构建上下文 commit、基础镜像 digest 和持久归档 SHA-256。
不把镜像 tar、容器数据或本地密钥提交到 Git。

## 验收含义

- **PASS**：主仓库原始 SHA、标签、复现分支起点及可读取的逐层目标 SHA 已核对。
- **FAIL**：当前递归依赖完整性和整个工作树干净条件不满足，原因如上。
- **NOT TESTED**：未获取对象内的进一步嵌套依赖、Docker 和论文实验结果。

管理提交可用 `git log --format=fuller --grep='^chore: initialize research git workflow$'`
查询；运行实验时应另记录当时的完整 HEAD，不把管理初始化当作复现成功。
