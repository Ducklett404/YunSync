# 华为 AI 开发者空间与云端迁移说明

## 推荐流程

1. 本地完成功能开发和单元测试。
2. 将仓库克隆到 `/root/workspace/YunSync`。
3. 在开发者空间执行 `./start.sh`，检查 Linux 路径、编码、依赖和端口。
4. 保持 `USE_MOCK_AI=true` 完成基础闭环。
5. 先接入 OBS 私有对象读写，再依次接入 OCR、MaaS、RDS 和 DCS Redis，每次只替换一个适配器。
6. 构建 Docker 镜像并部署到长期运行的 ECS 或容器服务。

## 上云前检查

- `.env`、访问密钥和真实健康数据没有进入 Git。
- 所有测试通过，前端生产构建成功。
- 后端监听 `0.0.0.0`，提供 `/healthz` 与 `/readyz`。
- 数据库使用迁移脚本，不依赖手工建表。
- 只开放必要端口，数据库与 Redis 不直接暴露到公网。
- 演示环境只使用合成数据和匿名账号。
- 准备录屏和本地 Mock 降级模式。

## 服务替换关系

| 本地开发 | 华为云目标 | 配置位置 |
|---|---|---|
| SQLite | RDS PostgreSQL | `DATABASE_URL` |
| 可选本地 Redis | DCS Redis | `REDIS_URL` |
| 本地合成报告 | OBS | `HUAWEI_OBS_BUCKET` |
| Mock OCR | OCR 智能文档解析 | `HUAWEI_OCR_ENDPOINT` |
| Mock 文案生成 | MaaS | `HUAWEI_MAAS_ENDPOINT`、`HUAWEI_MAAS_API_KEY` |

M4A 已实现 `local_private` 与 `huawei_obs` 的适配器边界；本地验证使用 `USE_LOCAL_STORAGE=true`。云端切换时必须先设置 `USE_LOCAL_STORAGE=false`，补齐 OBS 鉴权实现并验证私有访问后，才可记录为真实 OBS 接入。OCR 同理：`USE_MOCK_AI=false` 后，未配置的适配器会返回 503，不会回退到未标记的合成结果。

M5A 已固定 `action-explain-v1` 提示词和服务端输出守卫。真实 MaaS 接入必须保留 `explanation_source`，对诊断、调药、极端方案和疗效保证继续执行同一守卫；模型不可用或输出不合规时只能返回标记为 `policy_fallback` 的固定解释。

M8A 已固定 `result-explain-v1` 和结果统计版本。迁移到真实 MaaS 后，模型只能改写服务端已计算结果，不能重新计算、补造数值或在数据不足时生成方向性结论。

M9A 已增加 PostgreSQL 离线迁移兼容、有界连接池、Redis TTL 降级、Production 演示数据门禁、脱敏云配置预检和备份恢复工具。真实执行顺序、回退边界与证据清单见 [CLOUD_OPERATIONS_RUNBOOK.md](CLOUD_OPERATIONS_RUNBOOK.md)；这些本地结果不能替代真实 RDS、DCS 和 IAM 验收。

## 建议保留的比赛证据

- CodeArts 需求拆解、代码生成和修复对话截图。
- 单元测试与前端构建结果。
- OCR 调用日志和用户确认页面。
- RDS、DCS、OBS 的资源截图及真实读写记录。
- 从零部署脚本和五分钟演示录屏。
