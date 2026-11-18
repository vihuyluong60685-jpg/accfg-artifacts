# 相关研究与 P2 定位

The Configuration Wall 已通过 ACCFG 捕捉显式状态，执行去重和配置计算重叠。本实验用相同两项 pass 在两条固定地址图中提前全部剩余字段，并检验其余真实部分时序。新证据主要缩小了字段级 Pass 值得研究的范围，而非证明一种新的通用调度收益。[The Configuration Wall](https://arxiv.org/abs/2511.10397)

通用 MLIR 软件流水或离线 List Scheduling 可实现已具备依赖与副作用模型的顺序。目标相关的 staging 存活、真正的捕获交接、单 owner、原子包和外部观察者仍需明确建模，不能直接以任意 LLVM 指令提前代替。AIDG 的资源/依赖图和 Autocomp 的实机反馈都是已存在的方向，本阶段通过同布局硬件可验证枚举界定收益，不以新命名制造算法创新。[MLIR 软件流水实现](https://github.com/llvm/llvm-project/blob/main/mlir/lib/Dialect/SCF/Transforms/LoopPipelining.cpp) · [AIDG](https://doi.org/10.1145/3715122) · [Autocomp](https://arxiv.org/abs/2505.18574)

P2 更合适的起点是配置接口与编译器协同。可描述明确提交点、原子字段组以及批量或描述符配置，从同安全基线比较动态写数、命令传输、捕获延迟、端到端周期与硬件复杂度。OpenGeMM 的现有 CSR/streamer 和 Gemmini 的命令接口可作为不同边界。P2 同样先做应用路径的主导开销审查，只有可验证的配置成本占比与接口原型数据才能支持系统性能主张。在此次两条图里，主机算子与数据打包仍优先占据优化预算。[OpenGeMM 原文](https://arxiv.org/abs/2411.09543) · [SNAX streamer](https://kuleuven-micas.github.io/snax_cluster/tutorial/streamer_design.html) · [Gemmini](https://github.com/ucb-bar/gemmini)
