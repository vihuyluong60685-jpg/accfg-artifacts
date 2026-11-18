# 公平对照与测量范围

研究分支 research/accfg-tradeoff-audit 从验收提交 cbf660f1cc73dfffd589541c9c382b346a7206fd 建立。五个子模块在原 checkout 按锁定 SHA 验证后只读导出。使用官方 Docker digest a3dd42b69696b63e3c83a1a1719c0b2ae1965673d60251c468b337b3bf9ad813，编译器 0df8b515768232036bceb6af7a6d5935b5e1a3db，OpenGeMM Verilator 5.026，其 ELF SHA 为 39ab1f5e980f8afb7e8f018c5a8678f93c26be96bff717af834c0223af7b29d9。主机 i9-13900HX/WSL2 约 8GB，容器上限 3GB、make -j1。[冻结配置](../../research/accfg_tradeoff_audit/configs/frozen.json)

| 对照 | 实际口径 |
|---|---|
| OpenGeMM 原 24 组 | A Base、B Dedup、C Overlap、D Both，16/32/64/128/256/512。重新解码原始 trace 与 ELF，逐值核对 PKL 和官方 CSR 写计数。原 no-copy 未开启 golden。 |
| OpenGeMM 新尺寸 | 24³、40³、24×16×32（N×K×M），四 flag。矩形明确给生成器与 gendata 同形，保留实际结果。no-copy 与 checked 各 12 次有效；8³、20³ 的 A 在两范围各构建失败（退出 2）。8³ 为 transform 的 NotImplementedError，20³ 为 stride_patterns 属性缺失。 |
| 外层标记及波形 | checked 16³ A–D 同一 C 标记脚本。B/D 同 ELF 开关 VCD。外层从调用前至最终 barrier 后，排除描述符初始化、golden 和加载。 |
| Gemmini 原比较 | 原 C GCC vs 原 MLIR→Clang/适配 C。32–512 共 10 格，指令计数器与 CPI=3 的吞吐估计单列。 |
| Gemmini 匹配 MLIR | 32/64/128。两组使用原 optimized 规则，共同 transform、canonicalize、LLVM 及链接，只改 ACCFG Dedup，common.mlir 逐字核对。32 另有两种开启 golden 的真实 Spike 测试。 |

原 no_opt.acc_dialect 目标缺 optimized 规则的 canonicalize 灌入，故本次从同一 canonical IR 分流，再量测对应 ELF。OpenGeMM 六尺寸完全复用，checked 的 16/32/64 无修改 A–D 数据与缩减图只作 P1 只读参考。P1 的 Guard、Omit 和 G 不进入原方法排名。编译、正确性失败和不支持运行单列，不进入性能排名。[OpenGeMM 明细](data/opengemm_cases.csv) · [Gemmini 明细](data/gemmini_cases.csv) · [完整退出码](manifests/run_status.csv)
