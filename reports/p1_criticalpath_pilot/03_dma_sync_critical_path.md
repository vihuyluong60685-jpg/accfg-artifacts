# DMA 与同步关键路径

16³ checked 在 D/E/F 上的运行周期为 **1664/1694/1680**。hart0 的 0x7c2 barrier CSR 到紧随指令的四段长间隔和为 **1521/1549/1560**。F 在长间隔之外省 23 cycles，间隔内多 39，最终慢 16。

对齐 hart1 DMA 提交、busy 轮询、最后一次 idle sample 和 barrier 候选。再用同一 Verilator 二进制读取 VCD 中真实 DMA busy 信号。同一 ELF 四次启用波形的区间与关闭波形一致。三个 checked 方阵还对齐本次无波形重跑。

| 16³ checked | 区间 cycles | 四段同步邻近间隔 | 其中 DMA busy | 其中 DMA 非 busy | 四段之外 |
|---|---:|---:|---:|---:|---:|
| D Both | 1664 | 1521 | 853 | 668 | 143 |
| E Guard | 1694 | 1549 | 857 | 692 | 145 |
| F Omit | 1680 | 1560 | 845 | 715 | 120 |

F 的 DMA busy 少 8，非 busy 多 47，净增 39。E 的窗口增加 28，其中 busy 多 4、非 busy 多 24。指令侧完整位于这些间隔内的 DMA 请求至 idle 样本和 D/F 都为 833 cycles。考虑跨边界请求后，按窗口裁剪为 878/870。证据支持**F 的退化集中在同步窗口内的 DMA 非 busy 阶段**。未隔离具体是 DMA 提交前备址、指令获取、不同线程相位、未捕获的共享端口等待或其他因素。

图用实际时间戳呈现程序顺序、配置状态、DMA 完成与同步依赖。跨 hart barrier 配对为推断，未采到的仲裁及完整临界路径不可定量。不能把每段间隔直接当成 DMA 时间。

[事件图](figures/event_timeline.png) · [周期分解](figures/critical_path_comparison.png) · [指令事件](data/event_timeline.csv) · [依赖边表](data/event_dependencies.csv) · [波形区间](data/wave_dma_breakdown.csv) · [解码边界](analysis/02_event_trace_analysis.md)
