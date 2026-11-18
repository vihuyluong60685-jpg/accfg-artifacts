# 已有工作与差异

**The Configuration Wall** 已提供状态 SSA、去重和整组重叠。实验证实它的 pinned whole-overlap 对带晚到 call 的整组保守处理。P1 v2 的增量是对字段级 capture/观察者关系的独立证据，并通过二进制匹配对照量化可获得的收益。拆分手法本身仍可看作一般调度的设备实例。[The Configuration Wall](https://arxiv.org/abs/2511.10397)

**通用 MLIR 软件流水与 List Scheduling** 已能在合法图上重排/流水化，不能仅凭使用关键路径或列表调度主张新颖性。可复用贡献必须给通用调度提供原本缺失的设备语义，包括某字段 staging 与 launch 捕获点、外部观察者、跨 hart 发布和设备原子写组。显式化后应以相同约束的通用调度为对照，测量自定义规则的增量。[MLIR SCF LoopPipelining](https://github.com/llvm/llvm-project/blob/main/mlir/lib/Dialect/SCF/Transforms/LoopPipelining.cpp) · [SNAX streamer 接口](https://kuleuven-micas.github.io/snax_cluster/tutorial/streamer_design.html)

**Autocomp** 用硬件反馈、自动搜索和正确性度量优化加速器程序。字段捕获、观察者及保守回退若能形式化，就是与搜索正交的 legality 约束。现阶段两者没有同目标公平比较。[Autocomp 原文](https://arxiv.org/abs/2505.18574)

**AIDG** 从硬件与指令结构建立性能模型。本阶段的忙闲相位和关联可以作为模型输入，但依赖图和事件分析本身已有先例。P1 v2 的实验结果主要约束的是收益归因和何时值得投资设备语义，未证明新的通用预测方法。[AIDG 原文](https://doi.org/10.1145/3715122) · [OpenGeMM 硬件原文](https://arxiv.org/abs/2411.09543)

论文级贡献仍需要至少一种有代表性的应用路径、可重用的接口语义、拒绝用例和同布局硬件验证。用配置写计数或原 S/G 总时长即可得出的结论，不应再包装成新调度贡献。
