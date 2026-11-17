# 05 Gemmini 复现

**PASS：五种规模的 C baseline 与 MLIR deduplicated 共十组均实际运行，所有 Spike 子进程退出 0。**
结果来自官方完整入口，不使用预置数据或替代依赖。

## 执行与数据来源

源码运行提交：`3958aeb14e48a917a1e43ebbb87290becd3cf110`。
入口日志：`reports/logs/20261117T055112Z_official-run-all_4fc66e/`；最终退出 0。
该入口已顺序完成 `./build.sh`、`make all_binaries_opt`、
`gemmini_get_all_numbers.py`、`plot_gemmini.py` 和 `show_results.py`。
Spike 和 libgemmini 来自固定官方镜像，原始 RoCC 依赖从官方 Zenodo 精确恢复。
本次只给父仓库采集代码增加退出码、指令范围和二进制哈希审计，没有改变论文算法或原有指标公式。

## 本次实测与论文口径

表中每个单元的两个值依次为 baseline / optimized。

| 规模 | 测量区间计数 | 全程序 RoCC 数 | 模型性能 ops/cycle（先取整） | 模型性能加速比 |
| --- | --- | --- | --- | --- |
| 32 | 117 / 85 | 12 / 12 | 137 / 171 | 1.248175182x |
| 64 | 120 / 89 | 12 / 12 | 379 / 406 | 1.071240106x |
| 128 | 607 / 167 | 30 / 26 | 419 / 482 | 1.150357995x |
| 256 | 1373 / 259 | 78 / 58 | 482 / 506 | 1.049792531x |
| 512 | 4159 / 482 | 258 / 178 | 500 / 511 | 1.022000000x |

按作者 `show_results.py` 的先取整性能口径，独立计算几何平均加速比为
**1.105375797367x**，提升 **10.537579737%**。
相对附录 10.5% 的绝对差为 0.037579737 个百分点，
在该一位小数的取整范围内；正文更粗略的 11% 与该结果也不矛盾。
若改用未取整模型性能，几何平均为 1.106171777877x；
这只是统计口径敏感性分析，不替换作者口径。

`ops=2N^3`，`BW_eff=16*rocc/(3*counter)`，`Ioc=ops/(16*rocc)`，
`P_model=round(1/(1/512+1/(Ioc*BW_eff)))`。
独立重写后等价于 `round(1/(1/512+3*counter/ops))`；
这里的 rocc 因子在两个中间量的乘积中消去，不把它误认为独立的性能测量。

必须区分：

1. `cycles` 为作者输出第一条 `Cycles taken` 的 rdcycle 测量区间计数，按作者 Spike 口径解释为指令数。
2. `traced_instructions_total` 为整个程序实际记录的指令行数，含启动和后面的 CPU 参考计算；
   512 两组分别为 1086239412 与 1086239413，不能用其比值替代论文的区间指标。
3. 乘以假设 CPI=3 并结合峰值 512 ops/cycle 后得到的是近似模型性能。
4. 本次没有真实芯片、NPU 或硬件周期测量。

## RoCC 分类审计

原始 `rocc` 列统计全部 unknown RoCC 指令，含 flush、循环启动及配置子类型，不是纯配置指令数。
真实日志核验 opcode 为 custom3 (`0x7b`)；`gemmini.h` 中普通配置 funct7=0，
WS 循环配置为 funct7=9–13。单独分类，不改写官方原始数据。
本轮官方 PKL 的 `custom0_funct7_zero_total` 字段为未使用 ISA 插槽的计数，
不能将其中的 0 解释为 Gemmini 没有配置指令。
补充审计在同一批二进制上运行，完成后由 `gemmini_opcode_audit.*` 提供分类，并追加最终交叉核验结论。

## 输出与可追溯性

- `artifacts/gemmini_results.pkl`：2094 字节，SHA-256
  `bd314aad6e4854d003a0cc69283c0ec6e2267d0376c0187ed882b538a03902a1`。
- `artifacts/fig10_bar_plot.png`：28615 字节；副本 `reports/figures/fig10_bar_plot.png`。
- `tables/gemmini_measured.csv`：完整原始指标、模型中间量、全程序指令数、实际子进程退出码和二进制哈希。
- `configs/experiment_run.json`：真实命令、源码版本、镜像、开始/结束时间、输出创建时间与 SHA-256。

本次使用 `run-all.sh` 的真实文件名 `fig10_bar_plot.png`；README 单独命令中的
`fig_10_bar_plot.png` 命名不同，未伪造第二次实验来凑名称。
图像已实际打开检查：五种规模、两个模式、模型性能标签齐全。
大小和内容检查通过后，该小型 PKL、CSV 和 PNG 纳入 Git；二进制与大型流式日志不上传。
