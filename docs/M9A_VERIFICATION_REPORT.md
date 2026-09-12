# M9A RDS/DCS/IAM 本地云就绪基线验证记录

> 日期：2026-09-12
>
> 里程碑：M9A
>
> 数据：仅合成配置、故障替身与本地数据库

## 1. 已完成范围

- Staging/Production 只接受 `postgresql+psycopg`，PostgreSQL 连接池设置容量、溢出、等待、回收和连接前探测；
- 修复 M6 历史数据回填在 Alembic 离线模式下访问数据库的问题，完整 PostgreSQL 空库迁移 SQL 可生成；
- Redis/DCS 适配层支持命名空间、JSON、TTL、短连接超时、健康状态和进程内 TTL 降级；
- 行动解释缓存不包含用户健康数据，命中后仍重新执行安全输出校验；
- `/readyz` 区分数据库与缓存状态，缓存失联时返回 `memory_fallback` 和 `degraded=true`，数据库就绪仍返回 200；
- Production 强制关闭演示登录与演示种子，并拒绝 SQLite、非 psycopg 驱动、通配 CORS、本机缓存和缺失云配置；
- `cloud-preflight-v1` 只输出脱敏配置状态；支持实例身份或部署平台环境注入凭据；
- PostgreSQL 备份/恢复工具从环境读取连接信息，命令参数不含密码，恢复要求目标数据库名完全确认；
- 环境模板、Compose、架构、API 契约、迁移说明和云操作手册已同步。

## 2. 自动化结果

| 检查 | 结果 |
|---|---|
| Python 编译检查 | 通过 |
| Pytest | 89 项通过；第三方依赖警告不影响结果 |
| PostgreSQL Alembic 空库离线 SQL | 通过；完整生成至 head，未建立网络连接 |
| SQLite 现有数据库升级与模型差异 | 通过；`No new upgrade operations detected` |
| Redis 正常、断连、TTL 到期和禁用模式 | 通过 |
| `/readyz` 缓存断连降级 | 通过；返回 200 与 `memory_fallback` |
| Production 配置与凭据门禁 | 通过 |
| 云配置预检 | 完整合成 Production 形态通过；Local 形态按预期拒绝 |
| PostgreSQL 备份/恢复 dry-run | 通过；命令行不包含密码，恢复需精确确认库名 |
| Vue/TypeScript 类型检查与生产构建 | 通过 |
| Git 差异格式检查 | 通过 |

## 3. 验证边界

- 没有创建、连接或修改真实华为云 RDS、DCS、IAM、OBS、OCR 或 MaaS 资源。
- PostgreSQL `--sql` 只验证空库迁移脚本可生成，不是空 RDS 实际迁移与启动成功证据。
- Redis 使用内存替身验证成功和故障路径，不是真实 DCS 网络、认证、TLS 或故障演练证据。
- 备份与恢复只执行命令生成和安全门禁 dry-run；没有把合成结果冒充真实备份可恢复记录。
- IAM 内容是最小权限与凭据注入流程基线，真实角色、策略范围和控制台证据仍待 M9B 完成。
