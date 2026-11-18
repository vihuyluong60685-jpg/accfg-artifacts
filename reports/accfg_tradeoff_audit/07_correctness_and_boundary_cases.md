# 正确性、可观察退出状态与边界

**CORRECTNESS RISK，已在合成但合法的 ACCFG IR 触发，并由固定 Verilator 上的真实 ELF 确认。** 不将该反例计为性能退化或用于 Pareto。[根因 IR 和运行片段](logs/boundary_evidence.txt)

| 夹具 | 循环次数 | A / B | C / D | 手工守卫 R |
|---|---|---|---|---|
| C 调用者读回退出 A/C 配置 | 0、1、3 | 每次数值与状态错误 0，退出 0 | 每次数值错误 0、状态错 2，退出 1 | 不适用 |
| 第二个 GEMM 在 IR 直接消费 scf.for 返回的状态 | 0、1、3 | 每次数值与状态错误 0，退出 0 | 数值错 **128/64/64** 项，状态均错 2，退出 1 | 三次均数值与状态错误 0，退出 0 |

夹具用独立缓冲和已知整数矩阵，包含本应保持 sentinel 的缓冲。C/D 在零次循环无条件预置首轮 setup，在非零时末轮 yield 变为未来 A/C，导致使用 SSA loop live-out 的后续 GEMM 写到错误缓冲。R 只在隔离的 IR 中加首轮非空及尾轮继续 guard，最后 yield 保留实际状态。它证实状态差异来自首尾变换，并未拿来当作正式基线或胜率样本。两种错误地址均在已分配的 guard 缓冲中，无越界解释。[原始夹具](../../research/accfg_tradeoff_audit/cases/live_consumer.mlir) · [修正对照](../../research/accfg_tradeoff_audit/cases/live_guarded.mlir) · [逐项计数](data/boundary_cases.csv)

首次消费者夹具错误地在非零趟也要求 sentinel row0 被写，导致 A/B 错报 64。修正参考后 A/B 通过，C/D 的真错误仍在，两次记录均保留。固定 FileCheck 的状态 tracing、overlap、reset 注入、dedup、RoCC 对均实际出口 0；首次相对路径失败亦保留。新目标运行测试涵盖动态索引、A/C 两字段、C 侧 CSR 读回和外部重设，复杂分支、未知副作用、写包仍部分是 IR 层证据。P1 的动态地址、观察者与否决数据单列。该固定版反例没有测试新版本或任意用户模型，也不推翻原方阵复现。[上一阶段只读证据](https://github.com/vihuyluong60685-jpg/accfg-artifacts/blob/289979d8491e6554a6a07a83a31193e78bfc100a/reports/p1_ablation_v2/04_negative_controls.md)
