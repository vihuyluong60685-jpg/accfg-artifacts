# 《The Configuration Wall》独立性能权衡审稿

**论文的 OpenGeMM 主要收益真实，并且有明确范围。** 原 A→D 六形状几何平均 **1.989×**，最高 **2.714×**。checked 往往仍快，但收益明显缩小。Gemmini 的总体结果是以 CPI 假定得到的吞吐估计，且比较了不同前端；同 MLIR 管线的纯去重在 32/64 不变，128 少 4 个 Spike 指令计数和 4 次区间 RoCC。**NO-GO，当前没有充分证据直接开展独立性能论文；有条件验证配置捕获与退出状态，作为 P2 候选。** [原论文](https://arxiv.org/pdf/2511.10397) · [严格对照](02_fair_baseline_design.md)

| 分类与发现 | 实证与边界 |
|---|---|
| CONFIRMED REGRESSION | 原图已呈现 Overlap 的小规模变慢，16³ **169→225**、32³ **608→671**。本次补足配置写、主机指令及循环最终 launch 后写证据，并在三个新 no-copy 形状复现方向。 |
| CONFIRMED TRADE-OFF | 同一 Overlap 使原 64³ **2624→2352 cycles**，纯配置写 **1600→1800**、主机指令 **2084→2284**、.text **11320→11420 B**。checked 前沿上 B 与 D 交换了周期、代码和配置活动。 |
| SCOPE EFFECT | 新三形状 C/A 从 no-copy 退化变 checked 提升。16³ B/D 内层 **1695/1669**、外层 **2449/2445**。波形解释差异集中于 barrier 邻近的 DMA 非 busy 时间，不等于设备 DMA 执行时间。 |
| MODEL LIMITATION | Gemmini 的 CPI=1/2/3/5 五尺寸 MODEL 几何平均约 **1.050/1.081/1.106/1.147×**。固定 CPI 假定和整体 C/MLIR 结果不等于纯去重或真实设备周期。 |
| CORRECTNESS RISK，已实测触发 | 合法 ACCFG 显式消费 loop live-out，原 C/D 数值错 **128/64/64**，A/B 和 guarded control 全过。0/1/3 趟读回证实实际 A/C 偏离预期。它是固定实现的边界回归，与原矩阵跑分分开。 |
| NO REGRESSION FOUND | 48 次全构建样本未确证跨规模稳健的大幅耗时或 RSS 退化。可见单 pass 额外时间、IR 和合成结构内存增长；部分矩形多 ABI 保存恢复，未知普通 spill。 |
| UNVERIFIED HYPOTHESIS | 无法把不同 ELF 的差异逐一分配给布局、寄存器、取指、软件提交和物理资源竞争。静态代码增长未证明缓存退化。 |
| NOT TESTED | 能量、功率、面积、频率、物理接口字节均 **NOT MEASURED**；完整部署延迟、分布性能和跨版本敏感性也未测。 |

作者明确限定 no-copy、Gemmini CPI、前端差异和适用接口，并讨论了流水的首轮预置。论文值得补充的是实际可观察退出状态、分尺寸最坏性能、代码与编译成本、匹配 Gemmini 控制及任务范围。对于实际 AI/NPU，优先级最高的是**保持后续算子数值正确**。具体性能风险是范围变大后收益收缩以及独立输入上固定策略反转，编译的几毫秒不是当前主瓶颈。

研究优先级为 **① 配置捕获/原子提交与活跃退出状态，② DMA 交接与实测关键路径，③ 小循环流水条件**。第 1 项优于继续追逐 P1 的微小字段调度收益，可从现有源码与真 RTL 验证开始。P2 若能让两类接口共享可执行语义契约，保证可见状态并证明系统价值，才具备独立发表空间。单个 bug 的守卫修复、静态体积猜测或未校准能耗不足以成篇。[详细排名与发表门槛](09_research_breakthrough_candidates.md)

实测新 24 次尺寸运行、4 次带外层标记模拟、2 个波形对照及 2 次全 VCD 归档重放、8 次匹配 Gemmini Spike、48 次全编译、12 组逐 pass、24 个分阶段后端/链接记录，另有正确性探针。构建边界、工具首试、真实正确性失败均有退出码。原论文三个图、PKL 与前序研究保持原位。[全部运行](manifests/run_status.csv) · [本地归档](manifests/archive.json) · [复跑命令](../../research/accfg_tradeoff_audit/README.md)

[指标覆盖](01_paper_metric_coverage.md) · [周期退化](03_latency_regressions.md) · [代码体积](04_code_size_and_instruction_cost.md) · [编译](05_compilation_overhead.md) · [DMA](06_dma_sync_and_system_latency.md) · [正确性](07_correctness_and_boundary_cases.md) · [Pareto](08_multi_objective_tradeoff.md)
