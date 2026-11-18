# P1 第二阶段最终审稿判断

**CONDITIONAL。** 提前写入有可重复的、独立于第一阶段动态指令数变化的周期收益。它在第二个真实数据依赖族中仍有小幅效果，部分短任务则完全持平。现在值得保留合法性分析和受控微基准，正式投入通用 accfg 优化 Pass 还缺应用级价值和可重用目标效果契约。

## 平台与证据

本阶段从已同步的 P1 提交 `75e16e3be1dbbe08280d1e22330dacafe477d17a` 分出 `research/p1-ablation-v2`，独立工作树 `/home/yanmo/research/projects/accfg-p1-ablation`。上游、原复现与 P1 第一阶段的分支均保留。读取原始 P1 ELF、IR、反汇编、双 hart trace、Verilator 日志与波形并验证 SHA；P1 对照用原 ELF 重放。新 fixture 在 i9-13900HX、WSL2 Ubuntu 22.04、Docker 29.9.3、固定镜像与 Verilator 5.026 下运行。编译器为 SNAX `0df8b515768232036bceb6af7a6d5935b5e1a3db`、Clang/MLIR 17.0.6、xDSL `791e89d87cc23303e9ce3ac2d7e48e25eecc0e03`。模拟器 SHA-256 为 `39ab1f5e980f8afb7e8f018c5a8678f93c26be96bff717af834c0223af7b29d9`。[冻结输入与工具版本](../../research/p1_ablation_v2/configs/frozen_inputs.json) · [实测环境](logs/environment.txt)

## 一、提前配置贡献多少

G-late 和 G 由同一链接产物派生。只交换 A/C 两条 CSR 写入和第一组三条 await 指令。调用目标和 PC、动态分支、寄存器、文件大小和其它字节均保持。原元数据选择族在 K16/32/64 × direct/4 B DMA 六组中，G 分别节省 **4、5、5、6、6、6 cycles**。同布局的加速几何平均 **1.016×**，原 S/G 为 **1.101×**。K16 补做跨晚到调用的同私有 ABI 移位，得到 **3、7 cycles**，其调用点 PC 随移动而变化。大部分原总差异位于严格早写对照所测效应之外。[原负载消融](03_overlap_causal_ablation.md) · [代表性字节与 IR 差异](logs/representative_diffs.txt)

## 二、减少 18 条动态指令影响多少

S-compact 保持晚到数据读后再写 A/B/C。在六格中，具体删除原 S 的六条保存、恢复与搬运每趟，三趟共 18 条，实测省 **20–38 cycles**。维持总指令数与静态位置的 S-reg 已省 **10–15 cycles**，从 S-reg 再压缩则省 **5–28 cycles**。所以可量化的是这套删指令、寄存器及相关时序干预。纯粹减少计数与内存流量/相位的独立效果不能完全分离。严格对照 G/G-late 的动态分支路径与操作数相同。[指令与 ELF 审计](02_instruction_layout_audit.md) · [动态统计](data/performance.csv)

## 三、布局控制后是否优于串行

是。G 对字节匹配的 G-late 在六个三趟组全部领先；G 对保持串行写入同时压缩到相同动态指令数的 S-compact 仍省 **3–8 cycles**。后者的绝对 PC 和 helper 编码允许变动，严格因果度量取前者。4 B DMA 的 K16 一趟在两个真实 B 地址选择上，G 和 G-late 均完全打平。3 趟的 DMA 忙闲阶段、staging 和读顺序通过同 ELF 波形确认。[软件与 VCD 时间线](figures/core_timeline.png) · [负控制](04_negative_controls.md)

## 四、第二个工作负载是否获益

有小幅效果。新链在生产者 GEMM 后读并重新打包 **全部 64 个 int32 输出**，消费者 GEMM 的 int8 A 内容和 A 地址均由生产者决定。B/C 可提前配置，晚到字段与原 P1 相反。在同布局对照中 K8 一趟为 **0**，K32 一趟为 **5** cycles，K32 三趟为 **4–6** cycles（约 **0.11%–0.16%**）。4096 B DMA 使 G 三趟提交到 idle 从 64 增到 418 cycles，严格收益仍为 6 cycles。全就绪 K64 的整组早写获益 9 cycles，K8 为 0；原 whole-overlap 已能生成全就绪 K8 的整组调度。两种安全可运行的拒绝对照覆盖全部字段晚到和 staging 观察者。[跨负载验证](05_cross_workload_validation.md) · [分组实测](figures/tensor_chain_grouped_cycles.png)

## 五、合法性能否自动分析

已验证固定 xDSL 能从 SSA 和同块操作位置自动区分 ready/late。只读探针给受审计的无 staging 副作用摘要时，分别识别 A/C 与 B/C 为可早写；没有摘要时对同一调用保守拒绝。全字段晚到、外部 staging 观察分别在真实执行中有校验并走串行回退。通用版本还需明确 capture、独占所有者、寄存器原子组、副作用、未知失效和同步发布，并处理拒绝路径。[只读分析和回退](06_auto_pass_feasibility.md)

## 六、已有研究中的可区分贡献

原 The Configuration Wall 的整组 overlap 在两个存在晚到 call 的实验中保守留下 setup。通用 MLIR 流水、列表调度与搜索方法能使用显式依赖；可区分的研究方向是向它们提供字段级硬件 capture、观察者、原子写组和跨 hart 发布约束，用实际硬件与同布局对照测量增量。仅加入依赖图或换一种调度顺序已有充足先例。[相关工作对照](07_related_work_and_novelty.md)

## 七、是否应开发正式 Pass

当前 **CONDITIONAL**。同布局控制与第二种真正不同的依赖均有正样本，支持进一步验证。跨族三趟严格收益约千分之一、短用例为零，且 external call 效果尚依赖手工审计。下一步是代表性模型路径上验证系统级收益和机会频率，同时将设备 capture 与效果契约固化并给保守回退做回归测试。先建立这个门槛，再决定是否把小型同块变换并入正式 pass。

## 执行记录与交付

正确性要求包括两次实际 GEMM 的完整 golden、两次 launch 的软件重建快照、最终 CSR readback、必要时完整源张量读取、DMA 源/目的/大小/idle/双 hart barrier，以及状态观察检查。69 次常规模拟、11 次波形重放均通过，共验 191 对 launch 快照，含开启波形的重复验证。所有纳入结果的模拟与波形解码以退出 `0` 结束。初始两套链式 ELF 的构建因裸机链接缺少 `memset` 退出 2，相关 L 依赖待构建退出 1；用显式初始化修复并成功重跑。xDSL 首次只读探针使用了错误版本的 Call 类名，退出 1，修正后通过。两次故意拒绝不可提前写入场景记录预期退出 1。

[周期与指令数据](data/performance.csv) · [正确性 JSON](data/correctness.json) · [运行命令和退出码](manifests/run_status.csv) · [报告产物 SHA-256](manifests/report_sha256.csv) · [本地 ELF、IR、原始日志和波形 SHA-256](manifests/local_artifacts_sha256.csv) · [复跑入口](../../research/p1_ablation_v2/README.md)
