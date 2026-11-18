# 指令与二进制布局审计

严格匹配组在同一原始链接产物上做固定长度字级重排。先检查 ELF32 RISC-V 可执行段、已知指令编码、函数单一直接调用和无分支保护段，再校验实际字节与反汇编一致。修改文件输出到新工作树，对照 ELF 原件只读。检查每次变更能用记录的 32 位指令列表逐字恢复，此外整个 ELF 包括符号表、其余函数和数据都逐字保持。未完成这些检查的产物不会作为严格控制。[实现](../../research/p1_ablation_v2/scripts/rewrite_elf.py) · [链式控制实现](../../research/p1_ablation_v2/scripts/late_chain_elf.py)

| 组 | 保持 | 干预与仍需考虑的因素 |
|---|---|---|
| G → G-late | 文件大小、段/函数地址、call/return、条件分支地址与目标、寄存器、动态指令多重集、下一次 launch 配置 | 仅将 A/C 两条 staging 写越过首个 await，仍在晚到读之前。局部取指次序及设备等待相位可以随干预变化，属于此实际干预的结果。 |
| G-private → G-full-late | 私有 helper 约定、寄存器、操作数、分支及目标、文件大小及函数地址 | A/C 移至晚到 helper 返回之后，必须重编码被移动的直接 JAL 指令，其目标不变。只在 K16 多趟加入此敏感性检查。 |
| S → S-reg | 文件大小、S 的每个指令槽、CSR 写与 launch/await 的 PC、控制流地址、每趟区间指令数 | s0/s1 的两次保存、两次恢复、两次搬运变为 NOP。a3/a6 持有 A/C，审计后的 leaf 以私有 t3 传递 slot/临时值；两处调用站点及 leaf 同步修正。仍改变部分寄存器编号、内存操作和指令资源。 |
| S-reg → S-compact | 私有 ABI、CSR/int 运算与语义、函数起点、后续符号、全文件大小 | 删除 6 条实际执行 NOP/趟，将填充放到 ret 后；直线路径与 JAL 槽前移，目标不变，不能排除指令相位。 |

已编译的 direct leaf 使用 a3 为临时，DMA leaf 用 a3 传 slot 并作为临时。leaf 都不使用 a6 或 t3。硬编码补丁限定在审计过的 ELF 实验实例。S-compact 保持串行 A/B/C 的顺序，不绕开真实 helper、同步、CSR 或 golden 检查。NOP 对照的效果只作为一种实测干预。

张量链的 G/L 通过同一方法把 B/C 越过 await。全就绪对照则移动 A/B/C；由于该对照三个字段都提前准备，另跑未改的官方 whole-overlap。原始 IR、lowered IR、逐指令反汇编、逻辑分支计数和原始 trace 可由结果链接还原。[代表性 IR/反汇编差异](logs/representative_diffs.txt) · [动态指令和 ELF 哈希](data/performance.csv) · [哈希和运行索引](manifests/local_artifacts_sha256.csv)
