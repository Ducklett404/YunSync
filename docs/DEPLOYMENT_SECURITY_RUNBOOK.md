# 部署、安全与性能运行手册

> 适用里程碑：M10A 本地基线与 M10B 真实 Staging 验收
>
> 当前边界：仓库已提供生产容器和代理配置，但本机没有 Docker，且没有公网 Staging、证书或监控平台，因此没有把静态配置冒充真实部署证据。

## 1. 生产容器基线

`Dockerfile` 使用前端构建与 Python 运行两阶段镜像；运行阶段使用固定 UID/GID `10001`，关闭 Uvicorn Server 响应头，并提供 `/healthz` 容器健康检查。Compose 对应用容器设置只读根文件系统、`no-new-privileges`、删除全部 Linux capabilities，只保留上传卷和 64 MB 临时目录的写权限。

有 Docker 的机器上执行：

```powershell
docker build --tag yunsync:m10a .
docker run --rm --entrypoint python yunsync:m10a -c "import sys; sys.path.insert(0, 'backend'); import app.main; print('import-ok')"
```

正式部署必须使用镜像摘要或不可变标签；镜像构建成功后还要执行镜像漏洞与密钥扫描。当前本机没有 Docker，这两项保留给 M10B。

## 2. HTTPS 与反向代理

复制 `deploy/nginx.conf.example` 到受控主机后替换域名和证书路径。应用端必须配置：

```dotenv
ALLOWED_HOSTS=staging.example.com
FORWARDED_ALLOW_IPS=CHANGE_ME_PROXY_IP
FORCE_HTTPS=true
EXPOSE_API_DOCS=false
RATE_LIMIT_ENABLED=true
```

只有受信任反向代理可以提供 `X-Forwarded-*`。`FORWARDED_ALLOW_IPS` 禁止设为 `*`；TLS 证书和私钥不得进入仓库。应用的 `/healthz` 与 `/readyz` 允许代理在内网使用 HTTP 探测，其他路径在 `FORCE_HTTPS=true` 时拒绝非 HTTPS 请求。

## 3. HTTP 防护

- `ALLOWED_HOSTS` 拒绝未知 Host；CORS 只允许配置的来源、方法和请求头。
- API 响应包含 CSP、`nosniff`、禁止 iframe、最小 Referrer 和 Permissions Policy，并设置 `Cache-Control: no-store`。
- HTTPS 响应增加一年期 HSTS。
- 进程内滑动窗口限流用于单实例兜底，返回 429、`Retry-After` 和剩余额度；多实例环境还必须保留 Nginx/API 网关或 DCS 分布式限流。
- 上传限制为 PDF/PNG/JPEG、5 MB、扩展名与文件签名一致；对象键和前端静态文件路径必须位于各自根目录。

## 4. 日志、监控与告警

应用继续输出不含请求正文和凭据的单行 JSON。建议在云日志平台建立：

- `event=request_failed` 或 5xx：5 分钟内连续 3 次告警；
- `event=request_slow`：P95 超过 `SLOW_REQUEST_THRESHOLD_MS` 告警；
- `event=request_rate_limited`：突增时检查滥用或容量；
- `/readyz` 的 `degraded=true`：检查 DCS 连接；
- 实例健康检查失败：触发替换或回滚。

真实日志采集、通知接收和告警恢复截图必须在 M10B 留证，本地日志事件不能替代真实告警。

## 5. 安全审计

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\scripts\security_audit.ps1
```

脚本依次扫描仓库高置信密钥、审计 Python 生产依赖和 npm 生产依赖。扫描结果只输出文件、行号与规则名，不回显疑似密钥。漏洞数据库会持续更新，发布前必须重新执行。

## 6. 本地性能烟测

启动使用合成数据的本地服务后执行：

```powershell
.\.venv\Scripts\python.exe scripts\performance_smoke.py --base-url http://127.0.0.1:8000 --concurrency 20 --requests 100 --p95-limit-ms 500
```

脚本创建 20 个短期合成会话，接受当前演示知情说明，对非 AI 的 `/api/v1/account/status` 测量 100 次请求 P95，并让 20 个会话并发访问 Dashboard。令牌和响应正文不会写入报告。本地结果不能替代公网网络、RDS/DCS 和多实例条件下的压测。

## 7. M10B 证据清单

- [ ] 生产镜像构建日志、摘要、SBOM、漏洞和密钥扫描结果；
- [ ] 公网 Staging 地址、有效 HTTPS 证书与 HTTP 重定向记录；
- [ ] 反向代理、Host、CORS、限流和上传边界实测；
- [ ] 真实 RDS/DCS 条件下的 P50/P95/P99、错误率和资源曲线；
- [ ] 20 个独立演示账号核心流程压测且无错误；
- [ ] 关键错误告警触发、送达、恢复和责任人确认；
- [ ] 回滚到上一不可变镜像的演练记录。
