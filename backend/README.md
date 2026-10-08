# YunSync M12 云后端

该服务把小程序现有的确定性食谱推荐迁移为可部署的 FastAPI API，并为华为云 RDS PostgreSQL、DCS Redis 和服务端天气代理预留正式连接方式。

## 已实现

- `GET /health`
- `GET /v1/context/today`
- `POST /v1/recommendations/today`
- `POST /v1/recommendations/pantry`
- `GET /v1/recipes/{recipe_id}`
- PostgreSQL/SQLite 数据模型、Alembic 迁移和 12 道 DEMO 食谱种子
- Redis/DCS 天气与推荐缓存、版本前缀、TTL、空结果缓存和接口限流
- RDS、DCS、天气异常的明确降级状态
- 只记录规则版本、候选 ID、结果 ID 和原因码的最小推荐审计
- 服务端天气密钥与无密钥前端 API

## 本地运行

```powershell
cd backend
..\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe scripts\seed_demo.py
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

默认未配置 PostgreSQL、Redis 和天气服务时，服务使用本地 SQLite 与有界内存缓存，`/health` 会诚实返回 `degraded`。这适合离线开发，不代表 RDS/DCS 已联调。

如本机安装了 Docker，可在 `backend` 目录运行 `docker compose up --build` 启动 PostgreSQL、Redis 和 API。仓库不包含真实云凭据。

## 配置

复制 `.env.example` 中的变量名到本地安全环境或 CodeArts 部署变量。生产环境至少需要：

- `YUNSYNC_DATABASE_URL`：RDS PostgreSQL 的 SQLAlchemy 连接地址；
- `YUNSYNC_REDIS_URL`：DCS Redis 连接地址；
- `YUNSYNC_WEATHER_API_URL`、`YUNSYNC_WEATHER_API_KEY`：服务端天气代理配置；
- `YUNSYNC_CORS_ORIGINS`：允许访问 API 的 H5 域名。

不要提交 `.env`、数据库密码、Redis 密码、天气密钥或 Terraform state。

## 测试

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest --basetemp .pytest-tmp-m12
```

测试覆盖五个路由、迁移、来源与版本、缓存命中和过期重建、空结果保护、过敏过滤、数据库故障、Redis 降级、限流和最小化审计。

## 数据边界

12 道种子食谱全部标记为 `isDemo=true`、`reviewStatus=demo`。生产模式须关闭 `YUNSYNC_ALLOW_DEMO_CONTENT` 并导入经授权、经专业签署的正式内容。API 请求只接受受控体感标签，不接收或保存用户完整健康描述。
