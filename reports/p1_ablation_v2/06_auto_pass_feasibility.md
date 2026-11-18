# 自动分析与 Pass 的可行性

Pinned whole-overlap 检查输入状态只有 launch 与 setup 两个使用，要求两者同块，然后沿整组 setup 的 use-def 收集依赖；晚到 `func.call` 被判有副作用后，整个 setup 留在原位置。P1 A/C 仍可用；这次张量链则 B/C 可用、A 晚到。在第二个真实链的 W 控制中验证过：原 pass 的诊断明确指出 `materialize`，W 与 S 的 CSR lowering 字节相同。[固定的原 pass](https://github.com/KULeuven-MICAS/snax-mlir/blob/0df8b515768232036bceb6af7a6d5935b5e1a3db/compiler/transforms/accfg_config_overlap.py) · [IR 现场与差异](logs/representative_diffs.txt)

只读分析探针用固定 xDSL 解析并验证 accfg IR。它在同一块里找唯一前驱 launch/capture、匹配 await 和状态使用，从 SSA 定义严格区分支配 launch 的字段与后置定义。它对没有显式可信摘要的 call 保留串行。授予经本 fixture 审计的「不读写 staging」摘要后，可识别 P1 的 A/C 与张量链的 B/C；晚到 helper 始终留在依赖发生的位置。全字段晚到时即使给 helper 同一摘要也应拒绝拆分。该探针的断言限定适用的极小 IR 形状，提供分析可行性证据，未改写 IR。[分析源码](../../research/p1_ablation_v2/scripts/legality_probe.py) · [实际分析结果](data/legality_decisions.jsonl)

可复用规则需要目标端提供 independently staged 字段、捕获转换和原子写组，以及硬件状态所有权。SSA 支配只证明值可用。还需给外部 op 表达 staging read/write、全失效、可能 launch、内存/别名和 DMA publish/wait 效果。当前 `accfg.effects` 的 NONE/FULL 可用于保守门槛，不能代替跨 hart 或约束为某个字段的摘要。候选必须保持两次 launch 的完整捕获快照、所有观察点和最终状态。遇到未知 effect、reset、别名、公用写者、不可拆包、多块或未验证 target，回退原始调度。

如果后续有更大的独立负载价值，最小实现可在现有 overlap 之后加同块规则，仅识别已描述可独立写的组，按支配、capture 和副作用切割一次 setup。无需改动已有 dedup 或引入成本模型。当前证据支持维护分析工具、正确性用例和实验变换，是否投入生产级 pass 以最终归因和独立负载效应判断。
