# G 部分配置调度与正确性

G 在固定 SNAX 编译器上用手工拆分的 accfg IR 实现。每趟计算两次真实 8×K×8 int8 GEMM。第二次 launch 的 A/C 来自已分配好的非重叠 L1 区间；B 由第一次 GEMM 输出第一个 int32 的奇偶选择。direct 路径在第一次 await 后直接读该输出。metadata-DMA 路径先由 hart0/hart1 barrier 交接，hart1 发起 4 字节 DMA、等待 idle，再经第二次 barrier 发布，hart0 读取目的地址。独立 golden 计算期望奇偶及完整输出，定时区间内使用硬件实际输出。

| 调度 | 在第一次 launch 和 await 之间 | 晚到数据读取后、第二次 launch 前 |
|---|---|---|
| S 串行 | 不写新指针 | 写 A、B、C |
| W 官方 whole-overlap | 同 S | 同 S |
| G 拆分 | 写 A、C | 写 B |

官方 `accfg-config-overlap` 的 use-def 检查遇到有副作用的 `func.call @pilot_late_b`，因此没有移动打包 setup。原 Base、Dedup、Overlap、Both 在此 fixture 上的 lowered IR 字节相同，W 与 S 的每组周期相同。G 的 lowered IR 哈希独立。E/F 是历史方阵手工参考，在此 fixture 不适用。[策略 lowering 日志](logs/policy_ir_verification.txt) · [最小 IR 补丁](../../research/p1_criticalpath_pilot/patches/partial_schedule.diff)

## 合法范围

三个指针分别映射到 0x3d2、0x3d3、0x3d4。streamer launch 0x3d5 和 GEMM launch 0x3db 的次序及两次 await 均保留。单 staging 在 launch 接受后可重写下一次的字段，正在运行的 streamer 使用先前接受的配置，第二个 launch 前要求 A/B/C 都已到位。验证限定为 hart0 独占写、各缓冲分离、固定其他字段、不跨 reset、不提前执行晚到调用。无法证明独占、staging 捕获语义、数据别名或不可见观察者时，应保留整组；Gemmini 的成对 RoCC 命令未纳入拆分。没有修改 RTL 或官方编译器源码。

## 五层检查

1. pinned xDSL 验证输入、调度及 CSR lowering，MLIR 17 验证后续 IR 并由 Clang 生成 ELF。
2. 双 hart trace 重建 **86 对** launch 可见 staging 快照，与预期逐字段相等；G 的 A/C 在第一次 launch 后、await 返回前写入，B 在实际读取后写入，每趟恰有两个 launch 和两次 await。DMA 路径核对提交、idle sample、晚到 load 的顺序。
3. 同一 G ELF 波形显示第一次 GEMM busy 为 21061–21064，A/C staging 分别在 21062/21063 改写。DMA busy 为 21112–21127，晚到 load 指令在 21138，B staging 在 21148，下一次 GEMM busy 从 21150 开始。波形开关对应同一 172-cycle 区间。
4. 全部 **44 次**成功模拟中，golden 和三个最终 CSR readback 的错误数均为 0。每趟比对两组各 64 个结果；两种 B 选择由三个种子覆盖。零趟两路各自保持初始 CSR 和未写输出 sentinel；一趟及三趟验证最后一次 launch 和最后 staging。
5. K64 设备端逐项参考计算首轮超时。改成独立 Python 生成整块参考数组，仍读取两次硬件输出、DMA 内容及最终 CSR。六个 K64 匹配 ELF 都使用相同 golden 实现。参考值切换在计时区间之外，ELF 排布可能变化，不能把重试前后当作受控周期对比。

[44 次结果](data/partial_comparison.csv) · [快照证据](data/partial_launch_snapshots.csv) · [硬件波形证据](data/wave_partial_proof.csv) · [同一 ELF 的实际输出](logs/partial_fixture_example.txt) · [fixture 源码](../../research/p1_criticalpath_pilot/cases/partial_harness.c)
