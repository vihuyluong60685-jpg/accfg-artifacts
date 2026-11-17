# 07 论文数值对齐

**PASS：375 项数值核对通过，0 项失败。**
结论来源于本次官方入口运行及独立公式重算，不以退出码或 PNG 文件存在作为唯一证据。

## 参照来源

- 论文 DOI：<https://doi.org/10.1145/3760250.3762225>。
- 作者公开 PDF：<https://arxiv.org/pdf/2511.10397>，携带相同 DOI，Figure 10–12 与附录 A.6。
  ACM 下载入口不可用时使用该公开版本；本地 PDF SHA-256 与 URL 见 `configs/paper_reference.json`。
- 逐项精确数字来自 `paper-original` 固定提交中的官方 README，不声称 PDF 图形公开了所有精确数字。
- 参照从 README 提取后独立比较；这些参考值没有写入任何实测 PKL 或作为实验成功替代品。

## 汇总结果

| 指标 | 论文附录 | 本次独立计算 | 有符号绝对差 | 相对误差 | 状态 |
| --- | --- | --- | --- | --- | --- |
| OpenGeMM 几何平均 | 1.99x | 1.988747921774x | -0.001252078226x | 0.062918504% | PASS |
| OpenGeMM 最高 | 2.71x | 2.714285714286x | +0.004285714286x | 0.158144439% | PASS |
| Gemmini 提升 | 10.5% | 10.537579736738% | +0.037579736738 个百分点 | 0.357902255% | PASS |

OpenGeMM 两个汇总指标参照值保留两位小数，取整容差为 0.005x；
Gemmini 提升参照保留一位百分数小数，容差为 0.05 个百分点。
容差在本次数据分析前按显示精度设定，没有调整算法或测量数值来满足容差。

## 逐项检查

`tables/paper_alignment.csv` 包含 Experiment、Matrix_Size、Optimization、Metric、
Paper_Value、Reproduced_Value、Absolute_Error、Relative_Error、Status。
Paper_Value 为兼容交付字段名：逐项值实际来源是官方 README，汇总项来源是附录 A.6。

- OpenGeMM：24 组 × 13 个字段 = 312 项，另加 2 个汇总项。
- Gemmini：10 组 × 6 个字段 = 60 项，另加 1 个汇总项。
- 共 375 项。README 六位小数浮点字段按 0.00000051 的绝对容差核对，整数计数也与对应值一致。
- 数值计算不依赖作者 plot/process 函数，独立重写 ops、Ioc、带宽、roofline、speedup 和 geomean。

单位按 Experiment 与 Metric 区分：OpenGeMM cycles 是仿真周期；Gemmini cycles 字段是作者
Spike 区间计数，按其指令数假设处理。ops/cycle 是模型或仿真性能，Ioc 为 ops/byte，
speedup 为无量纲，不跨平台直接比较这些原始数值。

## 统计方法和差异解释

Gemmini 主结果遵循作者先把每个 P_model 取整再求比值和几何平均的方式。
不先取整时结果为 1.106171777877x；
二者差异来自取整顺序，没有替换统计口径。正文约 11% 与附录 10.5% 的精度不同。

原始五个子模块完全一致；使用固定官方镜像及其中 GCC 13.2.0、Clang/MLIR 17.0.6、
xDSL 791e89d8、Spike 与 libgemmini 提交。没有替代依赖或算法补丁。
本次环境修复只涉及 Docker 组会话及缺失依赖恢复；Make 负载限制不改变编译或算法选项。

额外发现：README 的 rocc 列含所有 RoCC 指令。补充审计将普通配置、循环配置、启动及 flush 分开；
这些额外分类在论文中没有逐项精确参照，因此不编造 Paper_Value、不纳入上述 375 项。
根据作者公式，Ioc*BW_eff=ops/(3*counter)，rocc 因子在模型性能中消去；
更精确的配置分类影响中间量解释，不应无声明地修改论文复现公式。

**NOT TESTED**：真实硬件性能、作者未公开的更高精度图形数值、对 PDF 的逐像素比对。
