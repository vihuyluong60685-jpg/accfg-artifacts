# 正确性、可执行候选与硬件协议

A/Base、C/Both 的两组原生编译产物先分别通过两输入的完整数值门槛，随后执行余下矩阵。64 个生产者 int32、64 个主机中间张量、64 个消费者 int32、64 个最终 int8 与独立 Python 生成的完整整数参考逐项比较。目标报告错误 0，最终 A/B/C 硬件 CSR 读回为消费者状态。双 hart 指令 trace 确认每次主机中间算子读取生产者完整 64 个 word，在前一 await 与下一 launch 之间发布。计时区间内 hart1 无 DMA，且只有受控 hart0 写该设备。[正确性 JSON](data/correctness.json) · [源码与定点参考](../../research/p1_workload_gate/scripts/generate.py)

每次图执行重建两轮完整的 25 字段 staging 状态，检查 streamer 与 GEMM launch 处状态相同且与预期一致。指针 A/B/C 写入分别为 0x3d2–0x3d4。0x3d5 streamer trigger，0x3db GEMM trigger，波形进一步对齐实际 capture/接受及 busy 信号。首图启动捕获后才能写第二图；三个互不重叠的 SPM 缓冲地址可以独立 staged，所有 launch、await 和计算时点的依赖保留。Host helper 的对应反汇编不含 CSR、ecall 或其它直接/间接 C 调用，已限定仅在这两个受控计算实例中授予内存副作用摘要。设备外部 reset、其它写者、CSR 读观察、原子包等不在这份合法性保证内。[轨迹](data/hardware_events.csv) · [着陆指令样例](logs/linked_controls.txt)

同布局候选基于通过验证的 Both ELF，只在首个 GEMM launch 后重排三个指针写和三个 await 指令。若 MLIR C ABI 包装是只含单跳转的 thunk，则先核对实际目标再保持原样。每个补丁以旧字节重建整个 ELF，校验新 SHA，保持不相关字节、全部非局部代码 PC、分支路径、区间指令数和配置写数固定。没有用 NOP 填充。先妥善完成 Base/Whole 的真实结果校验，再比较所有 mask。

最终有 **20 次常规模拟、4 次同 ELF 波形重放**，每次包含两输入判断。**48 次图调用、96 个完整配置快照**通过。初版 ELF 衍生工具导入路径有误，14 次构建失败和两次缺失待测 ELF 的波形启动返回失败均已归档。修正挂载地址、识别 thunk 后完成全部候选。原生模型早期工具参数和模板失败同样保留退出码。[退出码与命令日志](manifests/run_status.csv)
