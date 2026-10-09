# YunSync M12—M13 云后端

该服务把小程序现有的确定性食谱推荐迁移为可部署的 FastAPI API，并为华为云 RDS PostgreSQL、DCS Redis 和服务端天气代理预留正式连接方式。

## 已实现

- `GET /health`
- `GET /v1/context/today`
- `POST /v1/recommendations/today`
- `POST /v1/recommendations/pantry`
- `GET /v1/recipes/{recipe_id}`
- `POST /v1/recommendations/natural`：一句话体感与现有食材，MaaS 辅助抽取和说明
- PostgreSQL/SQLite 数据模型、Alembic 迁移和 12 道 DEMO 食谱种子
- Redis/DCS 天气与推荐缓存、版本前缀、TTL、空结果缓存和接口限流
- RDS、DCS、天气异常的明确降级状态
- 只记录规则版本、候选 ID、结果 ID 和原因码的最小推荐审计
- 服务端天气密钥与无密钥前端 API
- MaaS V2 Chat 服务端调用；JSON Schema 严格校验、置信度门槛、超时重试、TTL 缓存和熔断
- 高风险、特殊人群、疾病/用药和过敏规则在模型前后执行；结果仅来自审核食谱库
- M13 输出审计只保存提示词版本、阶段、状态、食谱 ID 和版本，不保存原话

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
- `YUNSYNC_MAAS_API_URL`：已开通 Region 的 MaaS V2 Chat 完整地址；
- `YUNSYNC_MAAS_MODEL`：控制台“model 参数”的准确值；
- `YUNSYNC_MAAS_API_KEY`：同 Region 的 MaaS API Key，只能放在服务端安全变量。

华为云官方 V2 规范示例在贵阳一使用 `https://api.modelarts-maas.com/v2/chat/completions`，香港使用 `https://api-ap-southeast-1.modelarts-maas.com/v2/chat/completions`。请以实际开通区域与控制台调用说明为准。参见 [MaaS V2 官方调用规范](https://support.huaweicloud.com/model-call-maas/model-call-019.html)。本地未配置 MaaS 时，接口返回规则推荐并标记 `degraded: ["maas"]`。

不要提交 `.env`、数据库密码、Redis 密码、天气或 MaaS 密钥、Terraform state。

## 测试

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest --basetemp .pytest-tmp-m12
```

测试覆盖 M12 路由与 M13 自然语言路由、迁移、来源与版本、缓存、过敏与高风险过滤、模型非法输出、超时、熔断及最小化审计。

## 数据边界

12 道种子食谱全部标记为 `isDemo=true`、`reviewStatus=demo`。生产模式须关闭 `YUNSYNC_ALLOW_DEMO_CONTENT` 并导入经授权、经专业签署的正式内容。M13 自然语言 API 临时接收最多 200 字描述，发送 MaaS 前移除常见联系方式与证件号；日志、数据库和 Redis 不保存原文，Redis 键仅使用摘要。不要输入姓名或联系方式。MaaS 只返回受控标签与原因码；食材、用量、步骤和安全判定始终来自规则与审核库。
