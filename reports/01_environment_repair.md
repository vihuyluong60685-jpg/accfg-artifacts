# 01 环境权限修复

2026-11-17，执行环境：WSL2 Ubuntu 22.04.5，普通用户 yanmo。

## 实际诊断

- 初始 `docker info`：连接 `/var/run/docker.sock` permission denied。
- `sudo -n docker info`：需要交互密码；未索取或保存密码。
- Socket：root:docker，GID 1001，权限 0660，链接解析为 `/run/docker.sock`。
- `getent group docker` 已包含 yanmo，但原进程 `id` 不包含 docker。
- Docker context 为 default，未发现 DOCKER_HOST/DOCKER_CONTEXT 覆盖。
- 原因是会话组列表未刷新；无需 usermod、chmod 或重装 Docker。

## 修复与验证

用 `sg docker` 启动具有已授权 docker 组权限的普通用户进程。
`id` 显示 UID 1000，主组 docker；没有切换为 root。
该进程的 `docker info` 和 `docker run --rm hello-world` 均退出 0。
服务端为 Docker Desktop / Engine 29.9.3，WSL Integration 的 CLI/Socket/容器路径可用。
未通过 Windows GUI检查所有 Integration 设置。

日志：`reports/logs/20261117T053313Z_docker-group-check_143d8f/`，包含完整输出、退出码和时间。
辅助程序 `reports/scripts/docker_user.py` 对同样情况执行安全的组会话切换，
并以参数数组/正确 shell 引号传递 Docker 参数。长期使用可重新打开 WSL/VSCode 用户会话后再检查 `id -nG`。
加入 docker 组有接近 root 的能力；本次仅使用账户已有的组成员资格。

## 资源与安全边界

WSL 内存约 7.8 GiB、Swap 4 GiB，未修改。工作盘可用约 952 GiB。
未重装 WSL、Ubuntu、Docker；未改动 Windows CUDA、TensorRT、PyTorch 或 Conda。
未删除已有 Docker 镜像、容器、Volume 或虚拟磁盘。

状态：Docker 普通用户进程访问与 hello-world **PASS**；官方论文镜像及脚本另见 03 报告。
