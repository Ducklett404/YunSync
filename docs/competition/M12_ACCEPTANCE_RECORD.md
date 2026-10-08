# M12 华为云后端验收记录

更新时间：2026-10-08

## 当前结论

状态：**M12 工程实现和本地契约验收已完成；华为云 RDS/DCS 创建及云内联调待执行**

本记录不把本地 SQLite/内存缓存描述为华为云 RDS/DCS，也不把尚未购买的云资源描述为已经上线。

## 已完成交付

- FastAPI 独立后端和 `/health`。
- 今日上下文、今日推荐、食材匹配、食谱详情共四个业务 API。
- 食谱、节庆/节气内容和最小推荐审计数据模型。
- Alembic 首版迁移和 12 道明确标记的 DEMO 种子数据。
- PostgreSQL/RDS 连接适配；本地无 RDS 时使用 SQLite 并报告 `database_local`。
- Redis/DCS 缓存适配，包含版本前缀、TTL、空结果缓存、过期重建和接口限流。
- Redis 不可用时使用有界内存降级，并在响应与 `/health` 中报告 `cache` 降级。
- 天气凭据仅由后端环境变量读取；小程序云 API 请求不携带天气密钥。
- 小程序配置云 API 地址后调用后端；未配置或请求失败时保留原有离线确定性规则。
- 日志只记录请求 ID、路径、状态和耗时，不记录连接串、密钥或完整用户输入。

## API 清单

| 方法 | 路径 | 结果 |
|---|---|---|
| GET | `/health` | 已实现并纳入契约检查 |
| GET | `/v1/context/today` | 已实现并返回天气/节庆上下文及降级状态 |
| POST | `/v1/recommendations/today` | 已实现确定性排序、安全过滤和缓存 |
| POST | `/v1/recommendations/pantry` | 已实现现有食材匹配和过敏过滤 |
| GET | `/v1/recipes/{recipe_id}` | 已实现来源、版本、审核状态与空结果缓存 |

## 自动验证

2026-10-08 本地执行：

- 后端测试：`13 passed`。
- Alembic：从空数据库升级到 `20261008_0001`，三张表存在。
- 缓存：首请求 `miss`、第二次 `hit`、TTL 过期后重新 `miss` 并重建。
- 数据库故障：停止推荐并交给 `database_unavailable` 503 处理器，不返回候选结果。
- Redis 未配置：限流与缓存降级到内存，并明确标记。
- 小程序 TypeScript：`npm run type-check` 通过。
- M2—M6 与构建回归：见本轮最终验证结果。

当前 Codex 沙箱的 Python 事件循环无法完成最小 `asyncio.sleep(0)`，因此本轮使用同步服务层和 OpenAPI 路由契约测试；标准 ASGI 启动命令、Dockerfile 和部署配置已经提供，云上运行验证属于 RDS/DCS 联调与 M14 部署证据。

## 安全与隐私检查

- [x] 仓库没有真实 AK/SK、数据库密码、Redis 密码或天气密钥。
- [x] `.env.example` 只提供变量名和本地非生产示例。
- [x] 推荐审计不保存城市、体感标签原文或完整健康描述。
- [x] 前端没有天气 API Key 字段。
- [x] RDS、DCS 或天气失败时返回明确降级状态。
- [x] DEMO 食谱保留 `source`、`version`、`isDemo` 和 `reviewStatus`。

## 待云环境完成

- [ ] 团队确认华为云 Region、RDS/DCS 规格、计费方式和预算上限。
- [ ] 创建 VPC、子网、安全组、RDS PostgreSQL 和 DCS Redis。
- [ ] 通过 CodeArts 安全部署变量注入连接信息。
- [ ] 在 ECS 子网完成 RDS/DCS 内网连接、迁移、种子和故障演练。
- [ ] 保存云端 `/health`、缓存命中和降级日志证据。
