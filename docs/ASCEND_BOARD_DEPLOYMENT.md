# YunSync 昇腾开发板初步部署指南

本指南适用于同一局域网内的首次演示。完成后，用电脑或手机打开板子的 H5 页面，提交一句“有点着凉，想喝粥”，由板上的 FastAPI、PostgreSQL 和 Redis 返回推荐。演示使用仓库自带的 12 道 DEMO 食谱。板卡型号、系统镜像和实机运行结果待现场确认。

前端在 Windows 电脑构建，板上只运行静态文件服务和后端容器。默认配置通过 CPU 执行推荐规则，可以先跑通这条链路；需要演示 NPU 推理时，另见文末。

## 1. 确认板端环境

在板子的 Linux 终端执行以下命令。记下板卡型号、系统、CPU 架构、可用内存、磁盘空间，以及电脑能访问的板端 IP。下文使用 `192.168.1.100` 举例，请换成实际地址。

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

继续前先确认当前账号能访问 Docker 引擎，并且有 Compose v2、Python 3 和 Git。电脑需要 Node.js、npm 和 scp。首次在线构建需要板子能下载容器镜像和 Python 依赖，电脑能下载 npm 依赖。现场断网时，提前在相同架构的环境构建并传入 API、PostgreSQL、Redis 镜像，同时带上 H5 构建产物。

## 2. 在板上启动后端

先在构建 H5 的电脑上运行 `git rev-parse HEAD`，记下本次演示提交的完整 SHA。在板上用单独的目录检出同一提交。

```bash
git clone https://github.com/Ducklett404/YunSync.git ~/YunSync-demo
cd ~/YunSync-demo
read -r -p '输入本次演示提交的完整 Git SHA：' deploy_sha
git switch --detach "$deploy_sha"
git rev-parse --short HEAD
```

H5 将从板子的 8080 端口提供，API 使用 8000 端口。下面用单独的 Compose 配置文件把 H5 的实际来源加入允许列表。请在同一终端执行。

```bash
BOARD_IP=192.168.1.100
cat > backend/compose.board.local.yml <<EOF
services:
  api:
    environment:
      YUNSYNC_CORS_ORIGINS: "http://${BOARD_IP}:8080,http://localhost:5173"
EOF

docker compose -f backend/docker-compose.yml -f backend/compose.board.local.yml up -d --build
docker compose -f backend/docker-compose.yml ps
```

等 `postgres` 和 `redis` 显示 `healthy`、`api` 显示运行后，再执行下一步。API 启动时会执行数据库迁移并导入演示食谱。仓库的 Compose 使用开发模式和 PostgreSQL 的 `trust` 认证，这套配置仅用于可信局域网演示。 [Compose 配置](../backend/docker-compose.yml)

## 3. 在板上验收 API

在板子的 `~/YunSync-demo` 目录运行：

```bash
curl -fsS http://127.0.0.1:8000/health
python3 deploy/m14/smoke.py --api-base http://127.0.0.1:8000 \
  --allow-local-http --allow-degraded
```

先看健康信息中的 `dependencies.database` 和 `dependencies.cache`。本方案应分别显示 `postgresql` 和 `redis`，两项状态均为 `ok`。默认未配置天气服务和云端模型，总状态显示 `degraded` 属于预期。

再看验收脚本的输出。通过时会看到 `"result": "pass"`，检查项包括节日上下文、今日推荐、食材匹配和自然语言推荐。默认配置下，自然语言样例的 `maas` 字段应为 `rules_fallback`。 [验收脚本](../deploy/m14/smoke.py)

## 4. 在电脑构建 H5，在板上提供页面

在 Windows **PowerShell** 中执行。修改前两行的板端 IP 和 SSH 用户名，API 地址会在构建时写入前端产物。

```powershell
$boardIp = '192.168.1.100'
$boardUser = '板端用户名'
Set-Location 'D:\A_MyProjects\ICT\YunSync\miniapp'
$env:VITE_YUNSYNC_API_BASE_URL = "http://${boardIp}:8000"
npm ci
npm run build:h5
scp -r dist/build/h5 "${boardUser}@${boardIp}:~/YunSync-demo/"
```

在板上开一个终端，启动演示用静态服务，并在演示期间保持该终端运行。

```bash
cd ~/YunSync-demo
python3 -m http.server 8080 --bind 0.0.0.0 --directory h5
```

在同一局域网的电脑上打开 `http://192.168.1.100:8080`。在首页提交“有点着凉，想喝粥”，打开浏览器开发者工具的 **Network（网络）** 面板，确认 `POST /v1/recommendations/natural` 的目标为板子 IP 的 8000 端口、响应为 HTTP 200，且响应中有 `main.id`。这个请求可以验证页面使用了板端返回的食谱。

## 5. 现场排查与停机

| 现象 | 检查方法 |
| --- | --- |
| 构建报镜像架构不匹配 | 对照 `uname -m` 检查预制镜像。板端若为 aarch64，应准备 linux/arm64 镜像。 |
| 8000 端口没有响应 | 在板上运行 `docker compose -f backend/docker-compose.yml logs --tail=80 api postgres redis`，先看依赖健康状态和迁移错误。 |
| 板上验收通过，电脑打不开 | 在电脑 PowerShell 用 `Test-NetConnection $boardIp -Port 8000` 和 `Test-NetConnection $boardIp -Port 8080` 分别检查连通性，再检查网段、端口和板端防火墙。 |
| 页面有内容，但没有板端推荐请求 | 检查构建时的 API 地址，修改后重新构建并上传。若浏览器提示 CORS，核对地址栏中的协议、主机和端口与 `YUNSYNC_CORS_ORIGINS` 一致，重新执行第 2 步的 Compose 启动命令。 |

演示结束后，在静态服务终端按 Ctrl+C。在板端仓库根目录运行 `docker compose -f backend/docker-compose.yml stop` 暂停后端；下次使用 `docker compose -f backend/docker-compose.yml start` 恢复已有容器，再启动静态服务。

## 如果验收要求板端 NPU 推理

当前自然语言流程支持云端 MaaS 和规则回退。若要演示本地昇腾推理，先记录板卡型号、芯片、驱动、CANN 版本及可用内存；支持 `npu-smi` 的设备可运行 `npu-smi info` 查看设备状态。建议先把“一句话提取体感与食材标签”接到适配该板的模型，沿用现有标签校验、过敏过滤和规则回退。验收时，用同一次请求的板端模型执行记录及接口响应确认 NPU 实际参与。 [现有模型调用](../backend/app/maas.py) · [自然语言推荐流程](../backend/app/natural.py)
