# 审稿式结论

**CONDITIONAL。** 原方阵已复现写入更少却周期更长的案例。部分配置机制有真实依赖、可核验的早写窗口、两组硬件输出与运行后状态验证，也有匹配的模拟周期收益。现阶段的增量是证明在受限的 OpenGeMM staging 协议中存在整组合并遮蔽的调度自由度。从一个构造族与现有解释模型仍无法支撑独立论文的普适性主张。

## 与相关工作对比

| 相关工作 | 交集 | P1 已验证的区别及尚待验证的贡献 |
|---|---|---|
| The Configuration Wall | 显式配置状态、配置去重、计算与配置重叠 | pinned whole-overlap 因有副作用的 B 生产链拒绝整组 setup，G 在同样的 IR 和后端可拆出两个合法地址写。需要通用字段级 legality、自动生成和更广负载才能建立独立贡献。 |
| Autocomp | 自动寻找 CPU/加速器程序的调度和性能改进 | P1 手工指定字段级拆分，直接验证 CSR 捕获、DMA 发布和 live-out；未做端到端自动搜索，也未做相同目标上的实测比较。 |
| AIDG | 用依赖图建模硬件和指令时间 | 本次图为双 hart trace 与硬件 busy 波形联合诊断，直接关联配置与发布/launch。依赖图和预测公式本身不能构成创新。 |
| 通用 MLIR 软件流水 | 重排阶段并通过重叠改变关键路径 | P1 需要证明 staging 捕获、逐字段副作用和后续状态，另有跨 hart handoff。通用流水可作为调度后端或对照，需要比较相同安全约束下能自动得到的结果。 |
| 常规 List Scheduling | 按依赖、延迟及资源优先级发射 | 应比较同样的合法性、目标与权重下的简单贪心。潜在增量在设备状态和跨 hart 发布语义的表示、验证以及可测效果。 |

[The Configuration Wall](https://doi.org/10.1145/3760250.3762225) · [Autocomp](https://arxiv.org/abs/2505.18574) · [AIDG](https://doi.org/10.1145/3715122) · [MLIR LoopPipelining](https://github.com/llvm/llvm-project/blob/main/mlir/lib/Dialect/SCF/Transforms/LoopPipelining.cpp) · [OpenGeMM](https://doi.org/10.1145/3658617.3697652)

## 下一步和停止条件

1. 从 pinned `compiler/transforms/accfg_config_overlap.py` 的整 setup use-def 检查入手。用 `compiler/dialects/accfg.py` 的 SSA 状态与 `compiler/accelerators/snax_gemm.py` 的寄存器映射声明可独立 staged 字段、launch 捕获点、所有者及不可拆包。只沿已知支配、程序顺序和已验证完成依赖生成一个 early/late 候选，遇到未知副作用、reset、别名或其他写者便保留整组。用 `convert_accfg_to_csr.py` 后的指令序列与动态快照双重验证。
2. 新增两类用例。第一类是真实多算子生产消费链，包含由前一算子或描述符决定的实际缓冲选择。第二类是负控制与系统干扰，覆盖 ready-already、无 busy 窗口、连续 DMA、更长同步等待以及布局敏感重排。预先冻结对照与留出。加入同指令和近似同布局的移动时点消融，估计早写本身的贡献。
3. 强化正确性覆盖，加入条件分支、循环尾、异常路径 reset、未知外部函数、别名、其他写者与不可拆分 CSR 包的拒绝样例。对 Gemmini 独立建模成对 RoCC 写及采样协议。增加目标 DSL 层的 launch 恒等和 live-out 回归测试。
4. 当新负载持续有合法候选收益时，才投入通用 pass。只有策略在存在不同最优选择的独立工作负载上超过固定 G、固定 Both 或简单贪心，才值得继续复杂成本模型。若公平消融消除收益，或代表性负载几乎没有安全机会，停止性能优化主线。现在可以整理方法和可复现 pilot 章节，独立论文结果还缺自动变换、消融和跨负载数据。

[P1 合法性证据](04_partial_schedule_correctness.md) · [匹配实测](05_performance_comparison.md) · [模型评估](06_cost_model_assessment.md)
