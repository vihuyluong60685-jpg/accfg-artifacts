# 方阵基线复核

从 OpenGeMM PKL、区间 JSON、历史两套日志与 ELF 哈希独立复核 28 组，再重编译和运行同范围的 28 组。**每组 Verilator 退出 0，周期、配置 CSR、hart0 区间指令数均与历史一致。** E/F 是上轮的手工参考，按同一个 IR 编辑脚本复跑。

| Size | Scope | A Base | B Dedup | C Overlap | D Both | E Guard | F Omit | G |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 16³ | no-copy | 169 | 84 | 225 | 91 | 84 | 77 | N/A |
| 16³ | checked | 1802 | 1700 | 1778 | 1664 | 1694 | 1680 | N/A |
| 32³ | no-copy | 608 | 251 | 671 | 224 | N/A | N/A | N/A |
| 32³ | checked | 11985 | 11758 | 11882 | 11545 | N/A | N/A | N/A |
| 64³ | no-copy | 2624 | 1136 | 2352 | 968 | N/A | N/A | N/A |
| 64³ | checked | 85195 | 83424 | 84294 | 83460 | N/A | N/A | N/A |

- no-copy 按原微基准范围关闭 scratchpad 拷贝及数值校验，严格正确性排名标 N/A。checked 依原 C 程序比较 golden，区间包含相应 DMA 与同步。
- 16³ no-copy 的 F/D 为 77/91，少 12 个配置 CSR 与 12 条区间指令。相对 A 为 2.195×，相对 D 为 1.182×。checked 同样少 12 个写，F/D 为 1680/1664，相对 A 为 1.073×，相对 D 为 0.990×，F 的 regret 为 0.962%。
- 32³ 在两范围均 D 最快，64³ 在 checked 中反转为 B，D 慢 36 cycles（约 0.043%）。16/32³ 单开 overlap 在 no-copy 慢于 Base，在 checked 快于 Base。
- 按地址解码真正配置写，launch/await 另计。ELF 分别保留哈希，带 debug 路径的重编译与旧 ELF 不要求字节相同，以计数及区间对齐做结果核验。

[旧数据、加速比与 regret](data/baseline_comparison.csv) · [本次重跑](data/new_square_replays.csv) · [复核方法](analysis/01_baseline_reanalysis.md)
