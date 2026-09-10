# YunSync 环境与配置基线

> 版本：V0.1
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
- Production 必须设置 `ENABLE_DEMO_LOGIN=false`；演示登录不得进入正式环境。

任一条件不满足时应用直接拒绝启动，避免错误配置进入演示或生产环境。

## 3. 日志基线

- `LOG_LEVEL` 可为 `DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL`。
- API 日志使用单行 JSON，记录时间、级别、事件、request ID、方法、路径、状态码和耗时；未处理异常只追加异常类型，不写入异常消息或堆栈。
- 不记录请求正文、报告全文、授权头、Cookie、密钥、联系方式或健康备注。
- 调用方传入的 `X-Request-ID` 仅接受安全字符和 64 位以内长度，防止日志注入。
- 会话原始令牌、档案正文、初筛答案和上传文件名不得写入审计 payload。

## 4. 演示会话

- `ENABLE_DEMO_LOGIN` 控制演示账号入口，Local、DevSpace、Staging 默认开启，Production 强制关闭。
- `SESSION_TTL_HOURS` 范围为 1–72 小时，默认 12 小时。
- 演示账号不采集手机号、邮箱或真实身份；令牌存于浏览器会话存储，关闭会话后不会长期保留。

## 5. 启动与验证

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
