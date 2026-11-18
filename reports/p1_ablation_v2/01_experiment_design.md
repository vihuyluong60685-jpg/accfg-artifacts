# 实验设计与可追溯性

P1 第二阶段起点为验收提交 `75e16e3be1dbbe08280d1e22330dacafe477d17a`。新分支 `research/p1-ablation-v2` 从该点在 `/home/yanmo/research/projects/accfg-p1-ablation` 建立，跟踪个人 fork。保留 P1 worktree 和论文复现 checkout。五个目标 Git 对象均经过本地归档验证，实验只读挂载两棵旧工作树。用于 P1 六个匹配单元的历史 ELF、IR、反汇编、模拟日志和双 hart trace 分别通过既有文件哈希重新核验。[冻结输入、工具和 Git 对象](../../research/p1_ablation_v2/configs/frozen_inputs.json) · [容器实测版本](logs/environment.txt)

与第一阶段相同的 OpenGeMM Verilator 5.026 二进制和官方 Docker digest；SHA-256 为 `39ab1f5e980f8afb7e8f018c5a8678f93c26be96bff717af834c0223af7b29d9`。CPU 为 i9-13900HX，Windows 11/WSL2 Ubuntu 22.04，镜像内 Clang/MLIR 17.0.6，xDSL 固定到 P1 所用对象。新代码只在隔离目录保留。编译一次一个 job，基础 ELF 从 P1 复用，无 RTL 重建。区间为同一 harness 的两次 mcycle 读之间，正确性检查在区间之后。

主矩阵预定为 P1 六个形状/范围组合，seed 11、三趟。G-late 与 G 只交换 A/C 两条写入和第一组 await 三条指令。S-reg 改私有调用寄存器约定，将六条保存/恢复与搬运替换为 NOP 以保留 PC。S-compact 删除这些执行槽，在函数 return 后保留不可执行填充。K16 另用对称私有 ABI 路径比较跨 await 加真实晚到调用的移动。B 选择额外验证 seed 1 与 11 各一趟。独立族和故意不适合 G 的用例在另一个矩阵中。[主矩阵](../../research/p1_ablation_v2/configs/matrix.json) · [新增负载矩阵](../../research/p1_ablation_v2/configs/chain_specs.txt)

每个有效候选用 Verilator 输出的独立 golden 比较、两次 launch 的 staged A/B/C、最终硬件读回和双 hart DMA 校验进入可比数据。DMA 时验证源、目的、大小、idle、barrier 与依赖读；部分 trace 的 hart1 到达第一 barrier 早于 hart0 计时。波形开关对比区间、动态指令、配置写与 ELF SHA，再对齐实体 staged、GEMM busy、DMA busy、streamer busy 信号。程序退出、波形退出和拒绝退出均留痕。

主要因果对比为同布局 G-late − G。原 S 与 G 的差值含指令、布局与事件相位差。S − S-compact 量化一次具体的六指令/趟消除干预，S-reg 进一步提供固定 PC 的观测。考虑指令操作、移动点和机器状态的交互，本报告按干预分别报告周期，避免把未观测的分量强行拆成可加百分比。
