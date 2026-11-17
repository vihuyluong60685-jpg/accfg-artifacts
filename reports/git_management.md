# 科研 Git 管理约定

建立日期：2026-11-17（Asia/Shanghai）。本次不运行 `run-all.sh`、OpenGeMM、
Gemmini 或 Docker，不修复依赖，不修改论文算法。

## 初始检查与审计

已执行 `git status`、`git status --short`、`git branch -avv`、`git remote -v`、
`git log -5 --oneline`、`git rev-parse HEAD`、`git submodule status --recursive`、
`git config --show-origin --get user.name` 和相应的 `user.email` 查询。

- 初始分支：`main`，跟踪 `origin/main`；HEAD 为
  `ce1567e40962037cda59a236bea6e3458caeb63a`。
- 初始 `origin` 指向作者仓库；没有 `upstream`、`paper-original` 或复现分支。
- 父仓库初始没有已暂存文件、未跟踪文件或普通源码改动。
  `git status --short` 为 ` m gemmini-rocc-tests`。
- `gemmini-rocc-tests` 内部为 ` M riscv-tests`；更深层索引缺失及版本偏差
  详见 [baseline_versions.md](baseline_versions.md)。未删除、清理、重置或覆盖这些状态。
- 初始 `user.name`、`user.email` 查询均无输出且退出码为 1。
  随后用户明确提供真实配置，仅写入本仓库 `.git/config`：
  `vihuyluong60685-jpg` / `vihuyluong60685@gmail.com`。
- 完整初始命令输出、各子模块状态及可用索引的 SHA-256 保存在本地
  `.git/research-git-initial-state.json`，不会进入版本库或随 clone 传播。
  本文和版本表保存可共享摘要。该文件没有认证令牌或凭据内容。

初始最近五条提交：

```text
ce1567e update README with last reviewer feedback
f26a22a clean-up zenodo notes
96b11f2 add information on how to extract the Zenodo artifact
cc9f3e2 incorporate reviewer feedback
2b1887d fix spelling, add note for zenodo artifact
```

## 基线、分支和远程

- `paper-original`：固定论文主仓库 SHA
  `ce1567e40962037cda59a236bea6e3458caeb63a`；禁止移动、覆盖。
- `main`：保留作者基线，不在此直接开展本地研究修改。
- `repro/accfg-2026`：从论文 SHA 直接创建，用于环境、依赖、编译修复、
  实验脚本、结果处理和复现报告。当前嵌套异常仍保留，尚未复现成功。
- `research/config-overhead-optimization`：将来从经验证且已提交的复现节点创建；
  本次不预建、不修改算法。
- `upstream` fetch：<https://github.com/KULeuven-MICAS/accfg-artifacts.git>。
  本地 push URL 设为 `disabled://upstream-read-only`，禁止误推作者仓库。
- `origin`：用户确认的 Fork
  <https://github.com/vihuyluong60685-jpg/accfg-artifacts.git>。
  已通过 GitHub API 确认其为上述作者仓库的 Fork。
- 本地 `remote.pushDefault=origin`、`branch.repro/accfg-2026.pushRemote=origin`、
  `push.default=simple`；仅普通 push，不 force push。
- 本地 `user.useConfigOnly=true`，防止没有明确身份时自动猜测作者信息。
  原 `main` 的远程跟踪随 rename 变为 `upstream/main`。

远程、身份、推送保护均属于 `.git/config`，不会随 clone 传播；新环境须核实后重设。
本地标签也不自动上传。备份时显式推送复现分支和 `paper-original`，不使用 `--mirror`。

## 忽略规则与文件边界

检查过原 `.gitignore`、父仓库全部跟踪文件、`artifacts/` 及实验脚本的输出路径。
作者原有 `*.egg-info/**`、`**/__pycache__/**`、`*.pkl`、`*.pdf` 规则保留。
新增忽略 Python 缓存和虚拟环境、编译输出、仿真波形、容器本地数据与镜像归档、
密钥、临时日志和大型二进制数据。生成的 PNG 仅在 `artifacts/` 下忽略。

不整体忽略 `reports/` 或 `artifacts/`；`artifacts/.empty` 仍被跟踪。
Markdown 报告、普通 JSON 配置、小型 CSV 汇总表、分析脚本可以显式纳入版本库。
`reports/raw/`、`reports/logs/`、`artifacts/raw/` 和 `artifacts/intermediate/`
专供非版本化原始数据、日志和中间文件；需跟踪的摘要放在这些目录以外。
密钥规则优先于文件用途；只提交人工审阅过的无密钥环境模板。

`.gitignore` 不撤销已经跟踪的文件，也不按文件大小过滤；大体积文本或未知二进制格式
仍须人工检查。父仓库规则不管理独立子模块内部文件，后续修改子模块时须单独审查。
本次不删除或取消跟踪任何原始正式文件，不改子模块忽略规则。

每次暂存前先看 `git status --short`、`git diff`、文件内容与大小，
只用明确路径 `git add -- <文件...>`；本次不使用 `git add .` 或 `git add -A`。
暂存后检查 `git diff --cached --stat`、`git diff --cached`、`git diff --cached --check`，
确保没有意外 gitlink、密钥、原始数据或编译输出。
本次以 `git check-ignore` 验证忽略与可跟踪样例，并检查原跟踪文件没有新增匹配规则。

## 实验与 commit 的关联

1. 先提交该阶段代码和经过审查的配置；记录 `git rev-parse HEAD` 的完整 SHA，
   将其作为 `code_commit`，不要把实验后报告提交当作实验使用的代码版本。
2. 运行前记录 `git status --porcelain=v1`、逐个子模块实际 HEAD、
   `git submodule status --recursive`、子模块内部工作树状态、配置文件 SHA-256、
   镜像 digest/image ID、主机/工具版本、完整命令和时间。
   递归状态不全或 dirty 时不能宣称是干净且可复现的运行；若作诊断运行必须保留补丁和状态。
3. 每次实验建立唯一 run ID。把配置、`metadata.json`、小型 `summary.csv`、
   报告和分析脚本放到 `reports/<run-id>/`（本次未创建或运行实验）。
   metadata 至少包含 `run_id`、`code_commit`、`paper_original_commit`、
   `submodule_targets`、`submodule_actuals`、`worktree_status`、`config_sha256`、
   `image_reference`、`image_digest`、`image_id`、`command`、起止时间、退出码和数据位置。
4. 大型原始结果、波形和二进制归档存放在持久数据存储，报告记录稳定 URL、
   文件大小及 SHA-256；不能只有本地绝对路径。敏感日志不公开。
5. 实验后单独提交结果处理和报告；报告引用前述 `code_commit`、run ID、配置及数据哈希。
   结果报告提交 SHA 可从历史查询，避免把自身 SHA 写进同一提交造成自引用。

## 后续提交类型

| 阶段 | 提交信息 | 范围 |
| --- | --- | --- |
| Git 管理初始化 | `chore: initialize research git workflow` | 本次 `.gitignore` 与两份文档 |
| 环境和依赖 | `fix: resolve artifact dependency issues` | 经过验证的环境与依赖修复 |
| 实验运行脚本 | `test: add reproduction verification scripts` | 实际新增的运行与验证脚本 |
| 数据处理 | `analysis: add paper result comparison` | 对照、汇总及分析代码 |
| 复现文档 | `docs: add reproduction report` | 运行条件、证据、结果与限制 |
| 方法改进 | `feat: optimize accelerator configuration` | 独立研究分支上的算法改进 |

每个提交对应真实改动，不建空提交。提交前运行与变更相关的必要检查，
在提交说明或报告记录验证结果；环境修复和算法改进分开提交。
本次已知偏差不得暂存成已确认的复现依赖或复现结果。

修改子模块源码时，先在子模块自己的研究分支提交并推送到有权限的持久远程，
确认新 SHA 可从干净环境获取；若原始 URL 无法提供新提交，则审阅并更新对应层级的
`.gitmodules` URL。随后逐层提交父模块的 gitlink 和说明，直到主仓库。
任何只有本地提交、悬空提交或不可获取 SHA 的 gitlink 均不能作为可重复的研究依赖。

## 推送与认证

身份配置只负责提交署名，不等于 GitHub 认证。初始化提交经检查后，使用：

```sh
git push -u origin repro/accfg-2026
git push origin refs/tags/paper-original
git remote -v
git branch -vv
```

若因认证失败而未推送，保留本地提交，不改写历史、不向作者仓库推送。
当前环境未安装 `gh`；可另行安装 GitHub CLI 后执行 `gh auth login`，选择 GitHub.com
和 HTTPS，核实 `gh api user --jq .login` 是用户账户，再执行 `gh auth setup-git`，
重试上述推送。也可通过可信的凭据管理器配置 HTTPS 凭据；不把令牌写进 URL、
报告、命令历史或版本库。认证与实际远程同步结果以最终验收为准。
