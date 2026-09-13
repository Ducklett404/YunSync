# YunSync 参赛证据索引

> 日期：2026-09-13
>
> 规则：本地、合成和静态证据只证明对应工程边界，不能替代真实人员、专业审核或云端调用记录。

## 1. 需求、设计与代码追踪

| 主题 | 需求/设计 | 代码与测试 | 里程碑证据 | 提交 |
|---|---|---|---|---|
| 需求与安全起点 | `PRODUCT_REQUIREMENTS.md`、`UX_FLOW.md` | 前端路由守卫、合成走查 | `USABILITY_SIMULATION_REPORT.md` | `0322540`、`ef15291` |
| 身份、授权、档案 | `API_CONTRACT.md` | `identity.py`、权限测试 | `M3A_VERIFICATION_REPORT.md` | `218b59c` |
| 报告、OCR、逐项确认 | `DATA_DICTIONARY.md` | `report_service.py`、OCR 契约测试 | `M4A_VERIFICATION_REPORT.md`、`OCR_EVALUATION_REPORT.md` | `da1948a` |
| 行动治理与解释 | `ACTION_TEMPLATE_REGISTER.md` | 行动策略与输出守卫测试 | `M5A_VERIFICATION_REPORT.md` | `6efbf71` |
| 14 天实验 | `UX_FLOW.md` | 实验状态机、日程完整性测试 | `M6A_VERIFICATION_REPORT.md` | `216d6cb` |
| 每日记录与导入 | `API_CONTRACT.md` | 幂等、动态字段、导入测试 | `M7A_VERIFICATION_REPORT.md` | `b48e3f1` |
| 统计复盘 | `DATA_DICTIONARY.md` | 金标准、缺失、异常值、区间测试 | `M8A_VERIFICATION_REPORT.md` | `96c05af` |
| 云就绪基线 | `HUAWEI_CLOUD_MIGRATION.md` | 配置门禁、缓存降级、迁移工具 | `M9A_VERIFICATION_REPORT.md` | `ca1740b` |
| 部署与安全 | `DEPLOYMENT_SECURITY_RUNBOOK.md` | HTTP、路径、扫描、性能测试 | `M10A_VERIFICATION_REPORT.md` | `b76a4b7` |
| RC1 验收 | `DEFECT_REGISTER.md` | 三轮主流程、Edge 与断线烟测 | `M11A_VERIFICATION_REPORT.md` | `eaf0526` |

文件名均相对于 `docs/`，代码路径相对于仓库根目录。

## 2. M12A 材料索引

| 材料 | 文件 | 当前口径 |
|---|---|---|
| 项目报告 | `PROJECT_REPORT.md` | 内容基线，待官方模板 |
| 架构与技术说明 | `ARCHITECTURE.md`、`TECHNICAL_GUIDE.md` | 本地与目标云边界分开标注 |
| 用户手册 | `USER_GUIDE.md` | 只允许合成/脱敏演示 |
| 部署手册 | `CLOUD_OPERATIONS_RUNBOOK.md`、`DEPLOYMENT_SECURITY_RUNBOOK.md` | 云步骤已准备，真实证据待补 |
| 演示与降级 | `DEMO_RUNBOOK.md` | 讲稿和切换协议完成，视频/截图待录制 |
| 答辩题库 | `DEFENSE_QA.md` | 统一安全和证据口径 |
| 开源依赖 | `OPEN_SOURCE_INVENTORY.md` | 直接依赖清单，最终归档前重生成完整 notices |

## 3. 当前可复现证据

- 全量后端测试、数据库迁移检查、前端类型检查与生产构建；
- 合成主流程 3/3、Edge 三档分辨率和 API 断线页面；
- 仓库敏感信息扫描、依赖审计、文件路径与上传边界测试；
- PostgreSQL 离线迁移 SQL、缓存故障替身、备份恢复 dry-run；
- OCR 合成契约样例、统计金标准和 AI 高风险输出守卫。

这些结果应通过对应脚本重新生成，不能只展示本文文字。

## 4. 必须补充的真实证据

| 类别 | 所需证据 | 状态 |
|---|---|---|
| 健康治理 | 指导老师逐条审核、签字、日期和修改记录 | 未完成 |
| 可用性 | 3–5 人早期走查和 5–10 人封闭测试原始记录 | 未完成 |
| 云数据库/缓存 | RDS 空库迁移、DCS 断连、备份恢复和控制台记录 | 未完成 |
| OBS/OCR/MaaS | 私有对象、真实请求、脱敏样例、模型输出和调用标识 | 未完成 |
| 部署安全 | 生产镜像、HTTPS、漏洞扫描、公网安全和性能 | 未完成 |
| 可观测性 | 云日志、告警触发、送达与恢复记录 | 未完成 |
| 参赛格式 | 官方模板、截止日期、文件大小、命名和提交回执 | 未完成 |
| 展示 | PPT、3–5 分钟视频、离线视频、三轮计时表 | 未完成 |

## 5. 证据使用原则

1. 截图必须包含日期、环境和可核对标识，但不得包含密钥或真实健康信息；
2. 云调用证据需能关联请求 ID、服务名和时间，不能用 Mock 日志替代；
3. 测试通过数必须来自当前提交重新执行，不沿用旧数字；
4. 真实人员记录使用编号而非姓名，并按批准范围最小化保存；
5. 答辩中遇到未完成项应直接说明边界和补验步骤。
