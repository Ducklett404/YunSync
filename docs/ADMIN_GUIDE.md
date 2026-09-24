# YunSync V2 管理员手册

> 适用版本：V2.0。真实账号、域名和云资源由客户环境负责人填写。

## 1. 角色与权限

| 角色 | 允许操作 | 禁止操作 |
|---|---|---|
| 参与者 | 管理本人授权、报告、档案、方案和反馈 | 查看他人数据、发布专业内容 |
| 审核人 | 审核知识条目、安全规则及版本 | 代替参与者修改健康档案 |
| 运维管理员 | 部署、迁移、备份、监控和事故处置 | 日常读取业务正文 |

生产环境关闭演示登录和演示种子。审核账号与运维账号分离；离岗或职责变更后立即回收权限并保留记录。

## 2. 发布顺序

1. 按 `.env.staging.example` 在部署平台注入配置和秘密，不提交 `.env`；
2. 构建镜像，记录 `仓库:标签@sha256:摘要`、SBOM、漏洞和秘密扫描结果；
3. 使用独立迁移身份执行 `python -m alembic upgrade head`；
4. 部署应用身份，确认其不能修改表结构；
5. 通过反向代理开放 HTTPS，检查 `/healthz`、`/readyz`；
6. 用监控令牌从受控网络抓取 `/internal/metrics`，完成告警送达演练；
7. 执行 `python scripts/release_preflight.py --env-file <受控配置>`，保存脱敏输出；
8. 按 `V2_M8_CUSTOMER_ACCEPTANCE.md` 见证验收后再切换正式流量。

## 3. 日常检查与处置

- `/healthz` 仅表示进程存活；`/readyz` 必须显示数据库就绪；
- 监控 `yunsync_http_events_total` 的失败、慢请求和限流事件；
- 每日检查备份任务，按既定周期在隔离环境恢复；
- 每周检查待审核、停用内容和来源版本；每月复核账号和秘密。

指标端点只输出聚合计数和路由模板，不输出用户 ID、报告 ID、正文、查询参数或凭据。监控令牌通过秘密管理服务注入并定期轮换。

数据库操作使用 `scripts/postgres_ops.py`。恢复前确认目标数据库名，先在隔离环境验证，并记录备份时间、恢复点、迁移版本、数据校验和执行人。发布回滚应同时检查镜像、迁移兼容性、知识内容和安全规则版本，不删除审计或历史方案快照。

隐私生命周期任务使用 `scripts/privacy_ops.py`。所有命令默认 dry-run；实际删除必须同时提供 `--apply` 和对应确认短语。按 `PRIVACY_OPERATIONS_RUNBOOK.md` 配置受控调度、最小权限、失败告警和执行证据，不在日志中记录用户 ID、文件名、对象键或健康正文。

详见 `DEPLOYMENT_SECURITY_RUNBOOK.md`、`CLOUD_OPERATIONS_RUNBOOK.md`、`CONTENT_OPERATIONS_RUNBOOK.md` 和 `INCIDENT_RESPONSE_RUNBOOK.md`。
