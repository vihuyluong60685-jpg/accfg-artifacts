# 三个可验证的研究方向

创新性、重要性、可复现性、修改难度、软硬件协同和发表潜力逐项 1–5，难度 5 表示更困难。权重以可复现及系统价值为先。[完整排序](data/research_opportunity_ranking.csv)

1. **捕获与活跃状态语义下的配置流水。** 合法下游 GEMM 消费 loop live-out 时，固定版 C/D 错误 128/64/64 项，A/B/guard 通过。源码入口为 compiler/transforms/accfg_config_overlap.py 的 LoopLevelSetupAwaitOverlapPattern、compiler/dialects/accfg.py、compiler/accelerators/snax_gemm.py。第一组实验沿用同 canonical、同 launch 快照，覆盖零/小 trip、下游使用、未知观察和 reset，再跨第二个真实接口或负载验证。软件基线是 guard、peeling 或终态恢复，硬件可定义独立 staging、捕获/提交版本、原子包及完成令牌。原 16/32³ 的加写上界为每外层一次 25 写，删除它的周期收益与 guard 成本需要测量。跨 CSR 与成对 RoCC 的契约差异是主要技术风险。软件流水首尾处理已有先例；独立 SCI 需要比小修复更广的契约、验证和性能证据。**CONDITIONAL**。相对 P1 单做字段级调度，该方向直接解决已观测的功能错误。[经典软件流水](https://suif.stanford.edu/papers/lam-sp.pdf) · [固定 overlap 代码](https://github.com/KULeuven-MICAS/snax-mlir/blob/0df8b515768232036bceb6af7a6d5935b5e1a3db/compiler/transforms/accfg_config_overlap.py)
2. **DMA 交接与可重叠区间的观测。** 16³ 相同标记 B/D 内层差 26 外层差 4，DMA busy +4 同时非 busy −28。原因已经定位到同步邻近，尚未独立定位物理仲裁。软件入口是 compiler/transforms/insert_sync_barrier.py 与现有重复测量；在相同地址布局、状态捕获、DMA 次数下单独移动发布点，加入有实际 DMA 的第二类任务，硬件比较显式完成通知。经验外层观测仅 4/2449 即 0.163%，待扩大。语义也可纳入 P2，但跨负载增益风险大，且 accelerator 同步接口已有研究。**CONDITIONAL**。[Mozart ASI](https://experts.illinois.edu/en/publications/mozart-taming-taxes-and-composing-accelerators-with-shared-memory/)
3. **小循环是否值得流水及工具成本。** C 在 16³、32³ 增 33.1%、10.36% 周期，原六形的 .text 多 100B，较大尺寸又能更快。最小改变在 accfg_config_overlap.py 依据已知 trip 及状态安全性保守启用，并固定 A/B/C/D 同流作基准，确认是否接近本实验已测合法前沿。可能探索有条件硬件 commit 降低 guard，但需要确认真实成本；当前全编译波动不支持复杂选择器。传统流水已处理许多类似问题。单独成篇 **NO-GO**，可作为第 1 项的低成本 baseline。

放弃以静态代码体积推断缓存退化、以指令数推断能耗、仅据小编译时间差做复杂模型。第 1 项是有更好复现基础的 P2 备选，论文价值仍取决于跨接口增量和可测应用结果。
