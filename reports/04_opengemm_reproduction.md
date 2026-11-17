# 04 OpenGeMM 复现

**PASS：6 个矩阵规模 × 4 个优化组合，共 24 组均从本次仿真生成，独立数值核对通过。**

运行来源：官方 `run-all.sh` 中 OpenGeMM 阶段；源码提交
`3958aeb14e48a917a1e43ebbb87290becd3cf110`，启动时父仓库工作树为空。
原始子模块与镜像 digest 见 02、03 报告。完整入口当时仍在进行 Gemmini，
其最终退出码另由 08 报告验收，不能把本阶段通过等同于整个入口通过。

## 实际执行路径

作者入口依次执行 `genbenchmark.py`，对规模 16、32、64、128、256、512
分别使用 `NO_ACCFG_OPT=1`、`DEDUP_ONLY=1`、`OVERLAP_ONLY=1`、`ACCFG_BOTH=1`，
构建、Verilator 仿真、解码 traces、逐组复制二进制和日志。随后执行作者
`get_all_numbers.py` 和两个 `plot_snax.py` 模式。所有实际编译命令保存在主运行日志。

这次使用作者原有 `NO_CHECK=1` 流程，移除 scratchpad 数据复制并测量 tiling loop；
不把关闭正确性检查的性能流程宣称为新增的数值正确性测试。
编译器和仿真器会产生原作者代码的警告，但未中止该阶段。
`logs/.rtlbinary` 写入警告不影响实际 traces，逐组二进制由作者脚本另行复制保留。

## 本次实测

| 矩阵规模 | 基线仿真 cycles | 组合优化仿真 cycles | 加速比 |
| --- | --- | --- | --- |
| 16 | 169 | 91 | 1.857142857x |
| 32 | 608 | 224 | 2.714285714x |
| 64 | 2624 | 968 | 2.710743802x |
| 128 | 12380 | 6036 | 2.051027170x |
| 256 | 65692 | 40196 | 1.634291969x |
| 512 | 393488 | 291302 | 1.350790588x |

独立计算：几何平均 **1.988747921774x**，最高 **2.714285714286x**。
相对于附录报告的 1.99x 和 2.71x，差异属于其保留两位小数的取整范围。
README 表格中 24×13 个逐项字段及两个汇总指标共 314 项均通过精度核对，没有改写测量值。

`ops=2N^3`，`speedup=baseline_cycles/optimized_cycles`，`P_meas=ops/cycles`，
`Ioc=ops/((5/8)*csrwi+4*csrw)`；另外独立检查配置带宽 2 bytes/cycle、峰值 1024 ops/cycle
下的顺序与并发 roofline。完整 24 组的 csrw、csrwi、cycles、ops、Ioc、性能与各模式加速比
位于 `tables/opengemm_measured.csv`。
`tables/opengemm_trace_audit.csv` 另记录整个 hart0 trace 的指令行数和二进制 SHA-256，
其计数包括启动代码，不等于 tiling loop 的指令数。

## 结果、真实性与归档

- `artifacts/opengemm_results.pkl`：本次生成，4447 字节；SHA-256
  `b98df083c2d786f924c2a667a4f5812d64ca46b61c129026bc11e481c8bcb0bf`。
- `artifacts/fig_11_bar_plot.png`：139642 字节；对应副本在 `reports/figures/`。
- `artifacts/fig_12_roofline.png`：128625 字节；对应副本在 `reports/figures/`。
- 原始 traces 与对应二进制：`snax-mlir/kernels/streamer_matmul/results/`，24 个组合目录。
- 完整命令日志：`reports/logs/20261117T055112Z_official-run-all_4fc66e/`。
- 独立分析日志：`reports/logs/20261117T060321Z_analyze-opengemm-stage_68d2ee/`，退出 0。

运行前清单只有 `artifacts/.empty`，没有 PKL、PNG 或旧结果；生成时间晚于本次运行开始。
两张图已实际打开检查；Figure 11 为六种规模的基线与组合优化对照，
Figure 12 按作者脚本只显示 64、128、256 的四种模式。
图表来自实际数据，不复制论文图片。这里的 cycles 和性能均为仿真结果，不是真实芯片实测。

经大小和内容检查，仅本次小型 PKL、CSV 和两张报告图纳入 Git；大型 traces 和编译产物留在本地，
其关联版本和哈希由最终结果清单记录。全局 *.pkl 忽略规则仍保留，该特定小型结果经显式审核暂存。
