# 配置权衡审计的输入、复跑与证据

从审计 worktree 根目录运行。原复现 checkout 的 HEAD 必须为 cbf660f1cc73dfffd589541c9c382b346a7206fd，仍需其原始 ELF、trace、PKL、PDF 与五个本地子模块。容器只读挂载该 checkout，并用 git archive 从每个固定子模块提交导出到容器临时目录。旧 P1 两份 checkout 只用于汇总原算法的既有运行。新输出写入审计目录下的 local/。环境为 Linux/WSL2、Docker 和固定官方镜像，每次容器至多 3 GiB，Make 单作业。分析使用 Python 3.10、pandas、pyelftools 和 matplotlib。[来源锁](configs/frozen.json) · [实验矩阵](configs/matrix.json) · [工具版本](../../reports/accfg_tradeoff_audit/logs/environment.txt)

## 编译和模拟

原版 OpenGeMM 六尺寸与 Gemmini 十格复用保存的证据。新增矩阵从空的 local/ 顺序执行。已验收审计的 local/ 保留历史检查点，完整复跑请使用该分支的另一个独立 checkout。open.sh 和 gemmini.sh 支持 DONE 检查点。每批 simulator 和编译子命令的参数写入相应目录，容器调用如下。

```bash
set -e
audit=research/accfg_tradeoff_audit
mkdir -p "$audit/local"
run_container() { bash "$audit/scripts/container.sh" "$@"; }
run_container open.sh extras     > "$audit/local/open_extras_host.log" 2>&1
run_container open.sh envelope   > "$audit/local/open_envelope_host.log" 2>&1
run_container gemmini.sh         > "$audit/local/gemmini_host.log" 2>&1
run_container open.sh compile    > "$audit/local/open_compile_host.log" 2>&1
run_container passes.sh          > "$audit/local/passes_host.log" 2>&1
run_container backend.sh         > "$audit/local/backend_host.log" 2>&1
run_container stress.sh
run_container boundary.sh boundary          > "$audit/local/boundary_host.log" 2>&1
run_container boundary.sh boundary_consumer > "$audit/local/boundary_consumer_host.log" 2>&1
run_container boundary.sh boundary_guarded  > "$audit/local/boundary_guarded_host.log" 2>&1
run_container disassemble.sh
```

归档采用两次额外波形重放。将相同 ELF 复制到单独子目录运行，逐字比较筛选结果和双 hart timing JSON。当前 rtl.sh 同时保留完整压缩 VCD 和筛选结果。首轮实测生成的 envelope 目录保留筛选波形，完整件位于 wave_retained。历史失败样本位于对应构建目录或 attempts/，退出码存于 .exit。8³、20³ 的两种范围执行了 Base 构建探针。边界夹具 C/D 的退出 1 是目标程序失败，套件记录各个退出码后继续。[运行摘要](../../reports/accfg_tradeoff_audit/logs/execution_summary.txt) · [全部退出码](../../reports/accfg_tradeoff_audit/manifests/run_status.csv)

```bash
for mode in B D; do
  src="$audit/local/envelope/checked_16x16x16_${mode}_r1"
  dst="$audit/local/wave_retained/$mode"
  mkdir -p "$dst"
  cp "$src/pilot.x" "$dst/pilot.x"
  run_container rtl.sh "/out/wave_retained/$mode" wave
  for item in vcd.csv trace_hart_00000.json trace_hart_00001.json; do
    cmp "$src/wave/$item" "$dst/wave/$item"
  done
  gzip -t "$dst/wave/full.vcd.gz"
done
```

## 从证据重建表格和图

```bash
repos=/home/yanmo/research/projects
audit=research/accfg_tradeoff_audit
report=reports/accfg_tradeoff_audit
export PYTHONDONTWRITEBYTECODE=1 MPLBACKEND=Agg
python3 "$audit/scripts/collect.py" "$repos/accfg-artifacts" "$audit/local" "$repos/accfg-p1-pilot" "$report/data"
python3 "$audit/scripts/loop_boundaries.py" "$report/data/opengemm_cases.csv" "$audit/local" "$report/data/loop_boundary_footprints.csv"
python3 "$audit/scripts/dma.py" "$audit/local" "$report/data"
python3 "$audit/scripts/graph_reference.py" "$repos/accfg-p1-workload-gate" "$report/data/prior_graph_phases.csv"
python3 "$audit/scripts/compare.py" "$report/data" "$audit/local"
python3 "$audit/scripts/plots.py" "$report"
python3 "$audit/scripts/evidence.py" "$repos/accfg-artifacts" "$audit/local" "$report/manifests"
```

evidence.py 从 SHA 清单逐成员校验本地归档。新增实验会改变本地件，应在独立副本生成对应新归档。历史迹线与 PDF 保留在原 checkout，哈希在历史输入清单。多指标表的 Path 和原始退出清单以 local/ 为基准，表中绝对路径指向只读旧输入，data/ 路径相对报告目录。论文覆盖表和科研排序是人工审读产出，数值 CSV 和 PNG 由脚本生成。[历史输入](../../reports/accfg_tradeoff_audit/manifests/historical_inputs_sha256.csv) · [本地文件 SHA-256](../../reports/accfg_tradeoff_audit/manifests/local_files_sha256.csv) · [归档校验](../../reports/accfg_tradeoff_audit/manifests/archive.json) · [审稿结论](../../reports/accfg_tradeoff_audit/10_final_critical_review.md)
