# 08 最终复现报告

**复现等级 A：原始依赖完整恢复，两个平台与三张图均实际完成，375 项指标在正确统计和取整精度内对齐。**
评价范围是论文官方 artifact 的仿真与性能模型结果；本次未开展算法创新或实机性能测试。

日期：2026-11-17（Asia/Shanghai）。项目：`/home/yanmo/research/projects/accfg-artifacts`。

## 逐项验收

| 问题 | 状态 | 实际结论 |
| --- | --- | --- |
| 环境是否修复 | PASS | 使用现有 docker 组的新进程会话，普通用户 docker info 与 hello-world 通过；作者 hello-world.sh 退出 0 |
| Git 代码是否可追溯 | PASS | 运行前工作树为空；论文基线、运行源码 SHA、逐层依赖、镜像 digest、配置与结果哈希均保留 |
| 原始或替代依赖 | PASS | 五个可达子模块全部精确匹配原始 SHA；RoCC 从官方 Zenodo 原对象恢复，无替代版本 |
| OpenGeMM 是否完整 | PASS | 六种规模 × 四种优化模式，24 组均编译、仿真、导出并验证 |
| Gemmini 是否完整 | PASS | 五种规模 × 两种模式，10 个 Spike 子进程退出 0；额外 10 组分类统计也退出 0 并交叉一致 |
| Figure 10–12 | PASS | 三张图从本次数据生成，实际打开检查并归档；不是论文图片或预置结果 |
| 数值对齐 | PASS | 375 项通过、0 项失败；新 opcode 分类不伪造论文精确参照 |
| 官方完整入口 | PASS | 仅运行一次 run-all.sh，真实退出码 0 |
| 完整复现与等级 | PASS / A | 满足用户定义的 A 级官方 artifact 性能复现条件 |
| 真实硬件与像素级 PDF 等同 | NOT TESTED | 本任务使用 Verilator、Spike 和模型，没有实机测量或像素级鉴定 |

## 核心实测结果

| 指标 | 论文附录 | 本次实测/模型 | 差异 |
| --- | --- | --- | --- |
| OpenGeMM 几何平均加速比 | 约 1.99x | 1.988747921774x | -0.001252078226x |
| OpenGeMM 最高加速比 | 约 2.71x | 2.714285714286x | +0.004285714286x |
| Gemmini 几何平均性能提升 | 约 10.5% | 10.537579736738% | +0.037579736738 个百分点 |

三个差异均在论文报告精度的取整范围内。逐项数据与误差见
[tables/paper_alignment.csv](tables/paper_alignment.csv)。
OpenGeMM 依据 Verilator 的 tiling-loop cycles；Gemmini 依据作者 rdcycle 区间计数，
假设 CPI=3 与峰值 512 ops/cycle，并遵循先取整模型性能再计算几何平均的原口径。
未取整的模型几何平均另为 1.106171777877x，不替代主结果。

Gemmini 512 的 baseline / optimized 区间计数为 4159/482；全程序指令数为
1086239412/1086239413；全部 RoCC 为 258/178；配置相关子类型为 215/135。
全程序计数含启动及 CPU 参考计算，不能替代论文所用的测量区间。
完整字段及分类见 `tables/gemmini_measured.csv` 和 `tables/gemmini_opcode_audit.json`。

## 版本与真实运行

- 原始主仓库与不变标签 paper-original：`ce1567e40962037cda59a236bea6e3458caeb63a`。
- 官方运行代码提交：`3958aeb14e48a917a1e43ebbb87290becd3cf110`。
- 补充分类统计源码提交：`8a306b829af5d9474ba200c4e385343b554cfb81`；原生工具源码/编译器/二进制哈希见 `configs/opcode_audit_context.json`。
- 官方镜像：`ghcr.io/kuleuven-micas/accfg-artifacts@sha256:a3dd42b69696b63e3c83a1a1719c0b2ae1965673d60251c468b337b3bf9ad813`。
- 官方完整入口：2026-11-17 13:51:12–14:21:09（Asia/Shanghai），约 29 分 57 秒，退出 0。
- 主运行日志：`reports/logs/20261117T055112Z_official-run-all_4fc66e/`。
- 补充分类日志：`reports/logs/20261117T060320Z_gemmini-native-opcode-audit_16c6d1/`，约 43 分 41 秒，退出 0。
- 运行前清单只有 artifacts/.empty；五个结果文件的实际创建时间、mtime 与哈希均已记录。

详细版本与证据分别见 [02 依赖审计](02_dependency_audit.md)、[03 官方环境](03_docker_environment.md)、
[04 OpenGeMM](04_opengemm_reproduction.md)、[05 Gemmini](05_gemmini_reproduction.md)、
[06 图表](06_figure_reproduction.md)、[07 对齐](07_paper_alignment.md)。

## 交付物与数据备份边界

- 原始 PKL 与官方 PNG：`artifacts/`。
- 三张图归档：`reports/figures/`。
- 全部测量 CSV、JSON 汇总、对齐表、opcode 分类与 SHA-256 清单：`reports/tables/`。
- 镜像、配置、参考来源、子模块锁与完整运行元数据：`reports/configs/`。
- 可复用命令审计、恢复依赖、统计和清单脚本：`reports/scripts/`。
- 原始 traces 与对应 OpenGeMM 二进制：`snax-mlir/kernels/streamer_matmul/results/`，约 385 MiB。
- Gemmini 二进制：`gemmini-rocc-tests/build/bareMetalC/` 与 `bareMetalMLIR/`。
- 官方归档、论文 PDF 与原生审计工具：`reports/raw/`，来源与哈希另有配置记录。
- 原始异常现场备份：`.git/reproduction-backup-20261117T133344/`。

经大小和内容检查，两个 PKL 合计约 6.5 KB，三张报告图合计约 297 KB，已纳入个人 Fork。
原始 RoCC Git bundle 约 22 KB，也已持久推送；未把只在本地的新子模块提交当作依赖。
大型 traces、编译文件和命令原始日志留在本地并记录路径、哈希、关联版本，未声称这些文件已全部远程备份。
Spike 逐指令流按官方方法流式消费，未将数百 GB 的流写成巨型日志；完整入口 stdout/stderr、实际计数和二进制哈希均保留。

## GitHub 同步与工作流

所有工作在 `repro/accfg-2026`，main、paper-original、各级 .gitmodules 和 gitlink 均未改写。
仅给父仓库采集/分析增加审计字段、退出码检查和辅助脚本；论文编译器算法与子模块源码未修改。
upstream 仍为作者仓库且本地推送地址被禁用；origin 为
<https://github.com/vihuyluong60685-jpg/accfg-artifacts.git>。
阶段代码、两平台 PKL、三张图、最终报告和表格通过普通 push 同步至个人 origin；最终以 HEAD 与 remote-ref 一致性核验确认同步。
最后一次核验保存在本地 `.git/reproduction-final-verification.json`，实际最新 SHA 同时由会话最终答复提供。
本报告自身的提交 SHA 用 `git log -1 --format=%H -- reports/08_final_reproduction_report.md` 查询，避免自引用。
此前阶段提交记录见 `tables/git_commit_history.csv`；完整历史用 `git log paper-original..HEAD` 查询。

子模块源码当前无修改；本地 info/exclude 仅屏蔽已审查的生成数据，未掩盖源码补丁。
生成文件所有者已恢复为 yanmo，未修改源代码内容；实验容器已停止并保留，镜像和数据均未删除。
原会话组列表仍可能陈旧，使用 `reports/scripts/docker_user.py` 或重新打开用户组已生效的会话。

## 后续研究入口

后续算法工作应从已验证的复现提交建立独立 `research/config-overhead-optimization`，本次未建立该分支或修改算法。

- `snax-mlir/compiler/transforms/accfg_dedup.py`：配置去重、跨控制流的冗余消除。
- `snax-mlir/compiler/transforms/accfg_config_overlap.py`：重叠调度、合法性与配置状态依赖。
- `snax-mlir/compiler/inference/trace_acc_state.py` 和 `compiler/dialects/accfg.py`：状态推断、效果表达及跨调用状态传播。
- `snax-mlir/compiler/accelerators/gemmini.py`、`snax_gemm.py` 及 lowering passes：不同加速器映射与代价建模。
- `accfg_artifacts/get_all_numbers.py`、`plot_gemmini.py`：保持原论文口径另行建立更精细的配置分类、CPI 敏感性与模型误差分析。

任何改进须与当前基线、相同规模和统计范围比较；子模块补丁需另行提交或归档并保证可获取。
