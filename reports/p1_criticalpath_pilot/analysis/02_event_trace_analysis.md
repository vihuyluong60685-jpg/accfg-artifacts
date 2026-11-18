# 事件解码、依赖与时间轴

- 0x3d5/0x3db 的写 1 是 streamer/GEMM launch，写 0 对应 await 序列中的 CSR。0x7c2 是 cluster barrier。依据固定镜像 snRuntime src/sync.h:65–67 和 gemm runtime src/snax-streamer-gemm-lib.c:47–79。其它参数准备未全量打标签。
- hart1 dmsrc/dmdst/dmcpy(i) 是软件可见提交。dmstati t0,2 与下条分支的 t0=0 给出 idle 样本，硬件完成可能早于采样。四段长间隔以 >100 cycles 选择，首段 D/F 各有一个跨窗口开始的请求。请求至 idle 及所裁剪的间隔均为 DERIVED。
- 取末次 idle 后同窗口出现的 hart1 barrier，配对到 hart0 的下一条指令。通常相差 2 cycles，该边为 INFERRED。资源仲裁和状态读取中的隐藏等待均未用时间相邻替代因果。
- 固定 Verilator 支持 --vcd。64 MiB 上限探测退出 153；知晓信号声明后改 FIFO，只保存 mcycle、GEMM/streamer busy、hart1 DMA busy、barrier out 与三个 staging 字段等，不重编 RTL。4 次 VCD simulator 和 parser 均退出 0。波形以同文件的 hart0 mcycle 对齐，稳定时相邻值隔两个 VCD tick；同 ELF 启用波形前后的区间 JSON 一致。
- 事件表中 MEASURED 为真实 trace 或波形，DERIVED 为运算所得，INFERRED 是依赖假说，UNKNOWN 无法测。关键路径比较图是观测分解，尚无完整物理 DAG。

[OpenGeMM 硬件协议](https://doi.org/10.1145/3658617.3697652) · [SNAX Verilator VCD 说明](https://github.com/KULeuven-MICAS/snax_cluster)
