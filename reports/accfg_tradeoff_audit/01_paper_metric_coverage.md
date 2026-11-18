# 论文指标覆盖矩阵

审计使用冻结的 16 页作者 PDF（与发表 DOI 对应）、正文、附录 A.1–A.7、原 README、生成器、计数和绘图脚本，以及验收日志与数据。章节覆盖 §2 的配置/数据区别、§4 的 roofline、§5 的 xDSL/ACCFG 语义与变换、§6 的实验、§7–8 与附录。图号按 PDF，HTML 图号有偏移。[原论文 PDF](https://arxiv.org/pdf/2511.10397) · [官方 artifact](https://github.com/KULeuven-MICAS/accfg-artifacts) · [20 项覆盖 CSV](data/paper_metric_coverage.csv)

| 主题 | 原文证据 | 审计结论 |
|---|---|---|
| OpenGeMM 性能 | PDF p275 §6.2、Fig. 11，p276 Fig. 12；附录 p280 A.6 | Verilator 周期覆盖 tiling loop，明确关闭 scratchpad 间复制。生成器的 NO_CHECK 同时关数值比较并从 IR 移除 memref copy。 |
| Gemmini 指令及吞吐 | p267 Table 1、p271 §4.6、p274–275 §6.1、Fig. 10 | Spike 指令精确。Rocket CPI=3 和峰值 512 ops/cycle 用于 Eq. (3)/(4) 的可达吞吐模型。作者已指出不同代码生成，还讨论恒量折叠、展开和小矩阵仅一次调用。 |
| 配置计数和流量 | pp269–271 Eqs. (3)–(8)、§4.6，绘图代码 | 论文定义模型等效字节。OpenGeMM 的官方 csrw+csrwi 包含 launch/await 写。本次另按地址重算纯 setup 写，缺设备物理总线字节计数。 |
| 流水首尾和小尺寸 | p274 §5.5、Fig. 9；p275 Fig. 11 | 原文写明循环外复制 setup、体内配置下一轮。图中可见 Overlap 部分小规模慢。末轮的动态冗余、状态合法性、栈和资源等待没有系统量化。 |
| 编译、静态体积与资源 | pp273–276；附录 p280 | 附录时间和磁盘内存要求针对 artifact。编译时间、峰值 RSS、运行时 .text 及 ABI/spill 未单列。 |
| 正确性、部署及 PPA | p273 §5.3–5.4；p274–275 §6；p280 A.3 | 论文描述未知调用的保守假设和仿真实验。未提供真实应用、芯片能耗或 PPA 数据。 |

CSV 每项独立标记 REPORTED、DISCLOSED_LIMITATION、NOT_REPORTED，并按审计证据标记 MEASURED_THIS_STUDY、NOT_MEASURABLE、NOT TESTED 或 MODEL。未评价维度不计为退化。能量、功率、硬件面积、频率和实际接口字节均标为 **NOT MEASURED**。CPI 灵敏度只有 MODEL，编译器版本保持固定。
