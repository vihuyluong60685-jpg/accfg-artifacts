# 历史实验独立对账

读原 PKL 并核对哈希 b98df083c2d786f924c2a667a4f5812d64ca46b61c129026bc11e481c8bcb0bf。原始 no-copy A–D 关联原 trace 和 ELF；checked 及 E/F 关联历史原日志哈希和区间。配置只含 0x3c0–0x3d4、0x3d7–0x3da 的写，启动和等待另行统计。测量窗口是 hart0 第二个区间。

每个 CSV 含 Base/Tvariant、Both/Tvariant、Tvariant−Tboth、配置写减少量和区间指令差。regret 仅在同范围、同负载同校验条件下比较，G 不在方阵的候选域内。checked 16/32/64 最快 D/D/B；no-copy 观察到 F/D/D。[主要结果](../02_baseline_comparison.md)
