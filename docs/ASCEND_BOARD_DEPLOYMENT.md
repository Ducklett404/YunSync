# 香橙派 AIpro 20T 部署指南

目标是在香橙派 AIpro 20T 的 ARM64 Linux 上运行 YunSync：H5、FastAPI、PostgreSQL 和 Redis 均在板上运行。推荐规则使用 CPU，默认无需配置天气或 MaaS。本次适配不包含 NPU 推理，未进行板卡实机验收。

部署入口为 [deploy/orangepi/board.sh](../deploy/orangepi/board.sh)，独立使用 [板端 Compose 配置](../deploy/orangepi/compose.yml)。浏览器通过 `http://板卡IP:8080/` 打开页面，H5 使用同源 `/api` 访问后端；板卡 IP 改变后无需重新构建。数据库和 Redis 只在容器网络内访问。

## 1. 板端准备

在板子的 Linux 终端运行：

```bash
uname -m
cat /etc/os-release
free -h
df -h .
hostname -I
docker info --format '{{.Architecture}}'
docker compose version
python3 --version
```

要求：

- CPU 架构为 `aarch64` / `arm64`；Ubuntu 或 openEuler 系统须已安装并启动 Docker Engine。
- 当前用户能执行 `docker info`，并安装 Docker Compose 插件 2.20 或更新版本（使用 `docker compose` 命令）。
- 主机有 Bash 和 Python 3；应用使用容器内的 Python 3.12、Node.js 22，避免更改板端系统 Python 和昇腾软件环境。
- 首次构建能访问 Docker Hub、npm 和 PyPI，并有足够磁盘空间保存构建缓存和数据。

Ubuntu 可按 [Docker 官方安装说明](https://docs.docker.com/engine/install/ubuntu/)安装引擎，Compose 见 [官方插件说明](https://docs.docker.com/compose/install/linux/)。openEuler 使用对应发行版提供的 Docker 安装方式，再确认以上命令通过。不同系统的包安装命令不应混用。若需要重启后自动运行容器，确认 Docker 服务已启用：

```bash
sudo systemctl enable --now docker
```

## 2. 将代码放到板上

如果适配文件已经提交到 GitHub，可以在板上克隆仓库：

```bash
git clone https://github.com/Ducklett404/YunSync.git ~/YunSync
cd ~/YunSync
```

如果适配仍是开发机上的本地修改，先将完整工作目录同步到板上。在开发机仓库根目录运行下面的命令，替换 SSH 用户和 IP。同步保留板上的 `.env` 和已有文件，不传开发机依赖、密钥与本地数据库：

```bash
rsync -az \
  --exclude='.git/' --exclude='node_modules/' --exclude='.venv/' \
  --exclude='dist/' --exclude='__pycache__/' --exclude='.DS_Store' \
  --exclude='.site-packages/' --exclude='.m14-venv/' \
  --exclude='test-results/' --exclude='playwright-report/' \
  --include='.env.example' --exclude='.env*' \
  --exclude='/backend/data/' --exclude='/deploy/m14/out/' \
  ./ orangepi@192.168.1.100:~/YunSync/
```

## 3. 构建并启动

在板上的仓库根目录运行：

```bash
cd ~/YunSync
bash deploy/orangepi/board.sh check
bash deploy/orangepi/board.sh init
bash deploy/orangepi/board.sh up
```

`init` 生成只允许当前用户读写的 `deploy/orangepi/.env`，包含随机数据库密码。重复运行不会覆盖该文件。默认网页端口是 8080；如被占用，先修改 `.env` 中的 `YUNSYNC_BOARD_HTTP_PORT`。

`up` 在板上构建 ARM64 API 镜像和 H5/Nginx 镜像，启动 PostgreSQL、Redis，执行迁移并导入 12 道 DEMO 食谱。数据库和缓存健康后才启动 API；API 健康后再启动网页，最后自动执行验收。首次构建耗时取决于板卡和网络。

完成后，在板上或同一局域网的电脑、手机打开：

```text
http://192.168.1.100:8080/
```

将 IP 替换为 `hostname -I` 显示且电脑可访问的板端地址。全部服务使用 `restart: unless-stopped`，Docker 服务启用后，未手动停止的容器会随系统恢复运行。

## 4. 验收

```bash
bash deploy/orangepi/board.sh status
bash deploy/orangepi/board.sh smoke
curl -fsS http://127.0.0.1:8080/api/health
```

验收经由 Nginx 的 `/api` 检查 PostgreSQL、Redis、节日上下文、今日推荐、食材匹配、自然语言推荐，并检查 H5 页面入口。通过时输出 `"result": "pass"`，数据库和缓存均为 `ok`。

默认天气、MaaS 未配置，因此 `/api/health` 的总状态为 `degraded`，自然语言推荐的 `ai.status` 为 `rules_fallback`，属于预期。验收脚本不会将数据库或 Redis 故障视为正常降级。

在页面提交“有点着凉，想喝粥”，用浏览器 Network 面板确认请求地址为板子的 `/api/v1/recommendations/natural`，HTTP 200 且响应含 `main.id`；进入食谱详情核对内容来自板端 API。当前内容仍为 12 道 DEMO 食谱。

## 5. 日常操作与备份

```bash
# 查看最近日志；也可在 logs 后添加 api / web / postgres / redis
bash deploy/orangepi/board.sh logs

# 暂停；需要恢复时再次执行 up
bash deploy/orangepi/board.sh stop

# 删除容器和项目网络，保留数据库与缓存卷
bash deploy/orangepi/board.sh down

# 同步新代码后重新构建、启动并验收
bash deploy/orangepi/board.sh up
```

已从 GitHub 克隆的干净工作目录可以先运行 `git pull --ff-only`；使用开发机本地改动时，先重新同步工作目录。`up` 会让网页服务随 API 更新重启，重新解析后端地址。

数据库保存在 `yunsync-orangepi_postgres-data`，缓存保存在 `yunsync-orangepi_redis-data`。备份数据库示例：

```bash
docker compose --project-name yunsync-orangepi \
  --env-file deploy/orangepi/.env -f deploy/orangepi/compose.yml \
  exec -T postgres pg_dump -U yunsync_app -d yunsync > yunsync-backup.sql
```

同时单独备份 `.env`。已有数据库时不要重新生成或随意更改其中的数据库密码；PostgreSQL 初始化变量不会修改已有数据卷的密码。`stop` / `down` 保留数据；不要对需要保留的数据使用 `down -v`。

可选天气服务或云端 MaaS 的配置见 `.env.example` 和 [后端说明](../backend/README.md)。修改 `.env` 后再次执行 `up`。默认配置用于局域网演示；公网发布使用原有 [M14 部署流程](../deploy/m14/README.md)。

## 6. 排查

| 现象 | 处理 |
| --- | --- |
| `check` 提示架构错误 | 确认系统和 Docker 引擎均为 ARM64；本配置固定使用 `linux/arm64`。 |
| `docker compose` 不存在或不支持 `--wait` | 安装或更新 Compose 插件到 2.20 或更新版本。 |
| 无法访问 Docker 引擎 | 先确认服务已启动、当前用户有访问权限。 |
| 拉镜像或安装依赖失败 | 检查板端 DNS、网络和镜像源；本流程首次构建需要在线下载。 |
| `up` 等待超时 | 用 `status` 和 `logs api postgres redis` 检查迁移、密码、磁盘空间和服务状态。 |
| 本机通过但局域网打不开 | 检查实际 IP、网段和 8080（或自定义端口）的防火墙规则。 |
| 页面打开但 API 报错 | 查看 `logs web api`，检查 `/api/health`。H5 应请求同源 `/api`。 |

## 实机记录

2026-11-25 本地验证：后端 34 项测试通过；前端类型检查和 `/api` 配置的 H5 构建通过；ARM64 / Python 3.12 二进制依赖下载通过；五个基础镜像均确认提供 `linux/arm64`；Compose 文件通过官方规范 Schema 校验；密码初始化、重复执行保留配置和验收脚本的依赖故障检测通过。当前开发机没有 Docker 引擎，未执行容器构建和启动测试。

板卡型号已确认：香橙派 AIpro 20T。系统具体版本、板端构建结果、接口和浏览器验收、重启恢复及数据持久化结果，均须在拿到板卡后记录。本地检查不能替代这些结果。
