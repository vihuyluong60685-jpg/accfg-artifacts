# 负载选择与冻结口径

本研究从 P1 第二阶段 `289979d8491e6554a6a07a83a31193e78bfc100a` 建立 `research/p1-workload-gate` 与独立工作树。五个子模块对象都从原 checkout 只读 Git archive 成功。保留第二阶段数据与源码哈希、官方 Docker digest、pinned SNAX 编译器 `0df8b515768232036bceb6af7a6d5935b5e1a3db` 和 Verilator 5.026，对照使用相同设备。实验执行前冻结图、输入、状态约束及时间边界。[冻结输入](../../research/p1_workload_gate/configs/frozen.json) · [预定矩阵](../../research/p1_workload_gate/configs/experiment.json) · [版本实录](logs/environment.txt)

| 负载 | 执行图 | 覆盖边界 |
|---|---|---|
| Mobile 瓶颈 | 2×4 NHWC、8 通道，OpenGeMM 1×1 投影，片上 CPU 量化与 ReLU6、真实带 padding 的逐通道 3×3，再一轮 OpenGeMM 1×1 投影、量化与残差相加 | 采用 MobileNetV2 瓶颈相关算子结构，通道缩至单硬件 tile、int8 合成参数，无训练准确率或完整模型数据 |
| 单头注意力 | 8 token、8 维，OpenGeMM QKᵀ、稳定逐行定点指数 LUT softmax、OpenGeMM PV 和输出量化 | 输入 Q/K/V 已提供，softmax 和两次 GEMM 均实际执行，范围为 attention 核心算子而非完整 Transformer |
| MLPerf Tiny AD01 | 官方 v1.0 预训练 int8 TFLite；动态批次和静态 batch=1 两条原生编译探测 | 两路径均识别 10 个 QMAC 为 SNAX GEMM，模板调度失败，周期及机会比例 N/A |

前两条图的数据依赖不同。Mobile 对邻域像素做深度卷积再融合残差，注意力在所有 token 间做归一化后加权。两者的依赖作用在输入内容，消费者地址由常规固定分配决定。第二阶段的动态地址探针单列校准，未加入新负载频率。两种固定种子 11/37 用于数值多样性和同布局相位观测。独立样本是两个拓扑、两个固定输入组合，共四格；复跑和十种策略不增加负载数。[MobileNetV2](https://arxiv.org/abs/1801.04381) · [Attention](https://arxiv.org/abs/1706.03762) · [MLPerf Tiny](https://arxiv.org/abs/2106.07597)

AD01 的 TFLite 下载和 TOSA 转换退出 0。接入 pinned 正确 MLIR 缓冲化序列后，两路径各有 10 个 `library_call = "snax_gemm"`，进到 `schedule-memref-linalg` 时均进入固定 tile 匹配中相等边界未实现分支并退出 1。没有可执行 ACCFG launch。适配至少涉及相等/不足边界的 tiling/padding、布局与 TCDM 规划以及端到端固件和独立 golden；不以估计替代运行或重写前端。[识别与映射状态](data/native_support.csv) · [官方固定模型](https://github.com/mlcommons/tiny/tree/v1.0/benchmark/training/anomaly_detection/trained_models)
