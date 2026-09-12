# YunSync 环境与配置基线

> 版本：V0.4
>
> 原则：模板只包含占位值，真实密钥永不进入 Git

## 1. 环境矩阵

| 环境 | 模板 | 数据库 | AI/OCR | 用途 |
|---|---|---|---|---|
| Local | `.env.local.example` | SQLite | Mock | 日常开发和自动化测试 |
| Development | `.env.example` | SQLite | Mock | 默认开发入口 |
| DevSpace | `.env.devspace.example` | SQLite 起步 | Mock，逐项替换 | Linux、路径、端口和适配器验证 |
| Staging | `.env.staging.example` | PostgreSQL/RDS | 可切换真实服务 | 演示前联调与压力测试 |
| Production | 不提供带值模板 | RDS PostgreSQL | 真实服务 | 正式部署；凭据由密钥服务注入 |

使用时把选定模板复制为 `.env`，再填写仅属于该环境的值。`.gitignore` 会忽略 `.env` 和所有 `.env.*` 实例，只允许 `*.example` 模板进入仓库。

## 2. 配置失败保护

`staging` 和 `production` 启动前必须满足：

- `SECRET_KEY` 至少 24 位，且不是仓库中的默认占位值；
- `DATABASE_URL` 不能是 SQLite；
- `CORS_ORIGINS` 不能包含 `*`；
- `ENVIRONMENT` 必须是已声明的环境名；
- `API_V1_PREFIX` 必须以 `/` 开头。
- `ALLOWED_HOSTS` 不得使用通配值，Production 还必须启用 `FORCE_HTTPS` 和 `RATE_LIMIT_ENABLED`、关闭 `EXPOSE_API_DOCS`，并把 `FORWARDED_ALLOW_IPS` 限制为实际反向代理地址。
- Staging/Production 只接受 `postgresql+psycopg://` 数据库驱动；连接池大小、溢出、等待和连接回收均有范围限制。
- `CACHE_ENABLED=true` 时 `REDIS_URL` 只接受 `redis://` 或 `rediss://`；云环境不能使用本机或占位地址。
- Production 必须设置 `ENABLE_DEMO_LOGIN=false`；演示登录不得进入正式环境。
- Production 必须设置 `SEED_DEMO_DATA=false`；不得自动写入合成演示账号与记录。
- Production 必须设置 `USE_LOCAL_STORAGE=false`；本地私有目录不能充当正式对象存储。
- Production 必须设置 `USE_MOCK_AI=false`；合成 OCR 不能充当正式处理结果。

任一条件不满足时应用直接拒绝启动，避免错误配置进入演示或生产环境。

云适配器启用时还必须提供项目 ID、私有 OBS 桶和对应 OCR/MaaS 端点。`HUAWEI_CREDENTIAL_MODE=instance_metadata` 表示使用运行实例身份；`environment` 表示凭据由部署平台环境或密钥服务注入，仓库模板中不得出现真实值。

## 3. 日志基线

- `LOG_LEVEL` 可为 `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL`。
- API 日志使用单行 JSON，记录时间、级别、事件、request ID、方法、路径、状态码和耗时；未处理异常只追加异常类型，不写入异常消息或堆栈。
- 不记录请求正文、报告全文、授权头、Cookie、密钥、联系方式或健康备注。
- 调用方传入的 `X-Request-ID` 仅接受安全字符和 64 位以内长度，防止日志注入。
- 会话原始令牌、档案正文、初筛答案和上传文件名不得写入审计 payload。
- 超过 `SLOW_REQUEST_THRESHOLD_MS` 的请求写入 `request_slow`；429 写入 `request_rate_limited`；5xx 写入 `request_failed`，供云日志平台建立告警规则。

## 4. HTTP 安全基线

- CORS 只开放配置来源及 GET、POST、PATCH、DELETE、OPTIONS，并只接受 Authorization、Content-Type 和 X-Request-ID 请求头。
- API 响应默认 `Cache-Control: no-store`，并包含 CSP、`nosniff`、frame、Referrer 和 Permissions Policy；HTTPS 响应增加 HSTS。
- 进程内滑动窗口限流只作为单实例兜底，多实例部署必须由受控 Nginx、API 网关或 DCS 提供共享限流。
- `/healthz` 与 `/readyz` 可供内网探针使用；Production 其他路径拒绝非 HTTPS 请求。

## 5. 演示会话

- `ENABLE_DEMO_LOGIN` 控制演示账号入口，Local、DevSpace、Staging 默认开启，Production 强制关闭。
- `SESSION_TTL_HOURS` 范围为 1–72 小时，默认 12 小时。
- 演示账号不采集手机号、邮箱或真实身份；令牌存于浏览器会话存储，关闭会话后不会长期保留。

## 6. 报告处理配置

- `USE_LOCAL_STORAGE=true` 仅用于 Local、Development 与 DevSpace 的合成文件验证；目录由 `UPLOAD_STORAGE_DIR` 指定且不进入 Git。
- `OCR_TIMEOUT_SECONDS` 范围为 0.1–60 秒，默认 8 秒；`OCR_MAX_ATTEMPTS` 范围为 1–4，默认 2 次。
- `MAAS_TIMEOUT_SECONDS` 范围为 0.1–60 秒，默认 8 秒；超时或输出校验失败时使用明确标记的固定解释。
- `USE_MOCK_AI=true` 时只运行确定性的合成 OCR 契约模拟；关闭后若真实适配器未配置，接口明确返回 503。
- Staging 模板关闭本地存储，但真实 OBS 和 OCR 在提供资源与凭据前仍不可用。

## 7. 启动与验证

Windows：

```powershell
Copy-Item .env.local.example .env
.\start.ps1
.\scripts\verify.ps1
```

Linux/DevSpace：

```bash
cp .env.devspace.example .env
chmod +x start.sh scripts/verify.sh
./start.sh
./scripts/verify.sh
```

容器环境启动前必须在本机 `.env` 或部署平台密钥设置中提供独立 `SECRET_KEY`。Compose 不再内置可用于 Staging 的默认密钥。

## 8. 云配置预检

```powershell
.\.venv\Scripts\python.exe scripts\cloud_preflight.py --env-file .env
```

预检只读取配置，不连接或修改云资源。输出只包含布尔状态、驱动名和凭据来源，不显示数据库、Redis、AK/SK 或 MaaS 密钥内容。检查通过只代表配置形态完整，不能替代真实 RDS/DCS/OBS/OCR/MaaS 调用证据。
