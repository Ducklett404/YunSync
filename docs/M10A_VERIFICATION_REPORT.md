# M10A 部署、安全与性能本地基线验证报告

> 日期：2026-09-12
>
> 结论：本地工程验收通过；真实镜像、HTTPS、监控告警和云端负载仍待 M10B

## 1. 本轮交付

- 生产容器采用前端/后端多阶段构建、固定非 root 用户、健康检查、只读根文件系统、`no-new-privileges` 和 capabilities 清理；
- Production 强制 HTTPS、关闭 API 文档、启用限流，并限制 Host 与可信代理；
- `cloud-preflight-v2` 把上述 HTTP 防护加入脱敏云配置预检；
- API 增加 CSP、HSTS 条件、安全响应头、`no-store`、429 恢复信息和慢请求/错误结构化事件；
- 保留 5 MB、格式、扩展名、文件签名和私有路径校验，并新增路径穿越测试；
- 增加仓库高置信密钥扫描、Python/npm 依赖审计和可重复的本地并发烟测脚本；
- 增加两项常用查询组合索引，并把图表库和 Vue 运行时拆成独立前端缓存块；
- 提供 Nginx HTTPS/限流代理示例和 M10B 真实验收清单。

## 2. 自测结果

| 检查 | 结果 |
|---|---|
| 后端自动化测试 | `103 passed` |
| Alembic upgrade/check | 通过，当前 head 为 `f9a0b1c2d3e4` |
| PostgreSQL 空库离线 SQL | 通过，包含新增索引且不连接伪 RDS |
| 前端类型检查与生产构建 | 通过，生成独立 `charts` 与 `vue-vendor` chunk；图表包 gzip 约 173 kB |
| Python 生产依赖审计 | `No known vulnerabilities found` |
| npm 生产依赖审计 | ECharts 升级到 6.1.0 后 `found 0 vulnerabilities` |
| 仓库敏感信息扫描 | 通过，0 个高置信发现 |
| 文件路径安全 | 路径穿越测试通过 |
| 本地非 AI 接口性能 | `account/status`，100 请求，P95 `120.19 ms`，阈值 `<500 ms` |
| 本地核心并发 | 20 个合成会话并发 Dashboard，`20/20` 返回 200 |

Dashboard 在本机 SQLite 与 Mock 解释条件下观测 P95 为 `1089.61 ms`。计划书的 500 ms 门限只适用于非 AI 普通接口，因此该值不作为本轮失败条件，但必须在真实 RDS/DCS、云主机与公网条件下继续采样和优化。

## 3. 依赖整改记录

首次审计识别出虚拟环境内旧版 `pip`、`setuptools`、`pytest` 以及 ECharts 5.x 的已知问题。已完成：

- 将 pytest 和 pip-audit 移到 `requirements-dev.txt`，避免测试工具进入生产镜像；
- 本地工具升级到已修复版本；
- ECharts 升级到 6.1.0，类型检查与生产构建通过；
- 重新审计 `requirements.txt` 与 npm 生产依赖，均未报告已知漏洞。

漏洞数据库会变化，该结论只代表 2026-09-12 本次联网审计结果，发布前必须重跑。

## 4. 未伪造的外部边界

- 本机没有 Docker，因此只验证了 Dockerfile/Compose 定义和自动化静态门禁，没有生成真实镜像构建或扫描记录；
- 没有公网 Staging、域名和证书，Nginx 文件不是 HTTPS 已上线证据；
- 没有接入云日志或通知渠道，本地 `request_failed` 等事件不是告警已送达证据；
- 20 个会话来自同一合成账号，不是 20 名真实用户或 20 个独立账号；
- 性能数据来自本机 SQLite 与回环网络，不代表 ECS、RDS、DCS 或公网表现；
- 没有把静态配置、合成会话或本地扫描冒充真实云端部署验收。

M10B 必须按 [DEPLOYMENT_SECURITY_RUNBOOK.md](DEPLOYMENT_SECURITY_RUNBOOK.md) 的证据清单重新执行并留存真实结果。
