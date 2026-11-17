# 02 依赖审计

2026-11-17。**PASS：全部已声明子模块精确恢复至论文目标 SHA，无替代源码。**
依赖恢复时构建尚待官方镜像就绪；现已完成后续构建与完整实验，结果见下及 03–05 报告。源码一致与实验通过分别核验。

| 路径 | 目标与当前实际 SHA（相同） | 来源 |
| --- | --- | --- |
| gemmini-rocc-tests | `4fec505cadacec4c371305b90973fa18758e9ac0` | 原始 GitHub |
| snax-mlir | `0df8b515768232036bceb6af7a6d5935b5e1a3db` | 原始 GitHub |
| gemmini-rocc-tests/riscv-tests | `c84daca8824635b7d896003c78f9c6245997cf7a` | 原始 Git 对象库 |
| gemmini-rocc-tests/riscv-tests/env | `0666378f353599d01fc48562b431b1dd049faab5` | https://github.com/riscv/riscv-test-env.git |
| gemmini-rocc-tests/rocc-software | `fddb795a0b52e82f8f4ce9ead9b1428440a62ab0` | 官方 Zenodo 原始 Git 对象及版本化 bundle |

原始 URL 见 [baseline_versions.md](baseline_versions.md)。每个子模块内部 `git status --porcelain=v1` 均为空。

## riscv-tests 诊断和最小恢复

原目录仅有 `.git` 文件，索引不存在，`git ls-files` 为 0；没有待保留的用户源码。
原 HEAD 为 `3df703cd52d5f0d8224e3c50bf03c6cb70efff98`，状态有 1425 项暂存删除标记。
先完整复制该子模块 Git 目录、工作目录和状态到本地
`.git/reproduction-backup-20261117T133344/`（约 3.5 MB 元数据）。
再使用目标树恢复索引和文件、切换为目标 detached HEAD；未使用破坏性清理。
之后 `submodule update --init --recursive` 精确获取 env，未使用 `--remote`。

## rocc-software 精确恢复

原 IBM 提交 API 返回 404；ucb-bar 对原 SHA 的提交查询返回 422。
优先读取 Zenodo 官方记录；API content 下载入口曾返回 403，改用官方 records 文件入口成功。
完整 208836477 字节归档通过发布 MD5 校验：`e58bd6e1f9d424bd80fd67536ce7ca04`。
SHA-256：`e4c241f84215954f031971c8f582d64cb713bd9f1716f721faeb7123d8a13365`。
仅从归档提取原始 Git 对象和引用，不执行其中的 hooks 或复制其中的配置。
通过 fsck、bundle verify、目标 SHA 与逐成员哈希核验，生成 22313 字节的可追溯 bundle。

bundle、来源和许可证位于 `reports/dependencies/`；恢复方法为
`python3 reports/scripts/restore_dependencies.py`。
原 `.gitmodules`、父仓库及所有嵌套 gitlink 全部保持不变。
只在本地 gemmini 配置中将 RoCC 的下载来源指向已验证 bundle。
没有源码补丁，没有用相似版本冒充原始提交；bundle 将随个人 Fork 持久保存。

## 审计证据

完整日志位于 `reports/logs/`，标签包括 preserve-dependency-evidence、
restore-riscv-paper-commit、zenodo-metadata、zenodo-download-retry、
inspect-zenodo-rocc-objects、verify-official-archive、recover-original-rocc-bundle、
verify-restored-dependencies。成功操作均有退出码 0；失败入口保留其真实失败记录。
元数据及哈希清单位于 `reports/configs/zenodo*.json`。

## 最终构建与依赖验收

官方 run-all.sh 已完整退出 0；Gemmini 的 C 与 MLIR 二进制均成功构建，OpenGeMM 的 24 组编译和仿真均通过。
所有五个可达 gitlink 再次逐层从原始 Git 树枚举，目标/实际 SHA 全部一致，内部工作树为空。
正式锁定记录为 `configs/final_dependency_lock.json`。本轮没有对子模块源码建立新提交或更新 gitlink。
