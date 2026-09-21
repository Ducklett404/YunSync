# YunSync 数据字典

> 版本：V1.1（含 V2 报告可比性、安全规则发布和 M4 内容知识库）
>
> 最新迁移：`f5a6b7c8d9e0_content_knowledge_base`
>
> 数据口径：开发与演示环境只保存合成数据

## 1. 关系总览

```text
user_profiles 1 ── N health_reports 1 ── N health_metrics
       │
       ├─────── 1 ── N auth_sessions
       ├─────── 1 ── N consent_records
       ├─────── 1 ── 0..1 food_safety_profiles
       └─────── 1 ── N experiments N ── 1 action_templates
                           │
                           └──── 1 ── N observations

audit_logs：独立审计事件表，通过 actor_id 与 payload 中的业务 ID 追踪操作。
safety_rule_releases：独立发布记录，由审核角色维护；同时最多一个活动版本。
evidence_sources 1 ── N knowledge_items（通过 payload.source_refs 的稳定引用校验）
knowledge_items 1 ── N content_reviews
```

删除用户时，会话、授权、报告、指标、食养安全档案、实验和观察记录通过外键级联删除；行动模板、知识条目、证据来源和审计日志不随用户级联删除。删除知识条目时，其审核记录级联删除。审计日志只保存最小事件元数据，不保存会话令牌、文件名、档案正文、食养风险详情、初筛答案、内容正文或审核资质正文。

## 2. `user_profiles`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK | 演示用户标识；当前固定为 `demo-user` |
| `nickname` | varchar(80) | 默认“演示用户” | 展示昵称，不应存真实姓名 |
| `role` | varchar(20) | 默认 `participant` | `participant` 或 `reviewer`，权限由服务端角色表决定 |
| `age_range` | varchar(20) | 默认 `25-34` | 年龄段，不保存精确出生日期 |
| `goal` | varchar(120) | 默认“改善日常活动习惯” | 健康行为目标 |
| `sleep_schedule` | varchar(120) | 默认空字符串 | 合成作息概况 |
| `activity_baseline` | varchar(160) | 默认空字符串 | 合成活动基础 |
| `constraints` | text | 默认空字符串 | 行动限制，不应填写诊断详情 |
| `preferences` | text | 默认空字符串 | 记录方式偏好 |
| `reminder_enabled` | boolean | 默认 true | 是否启用页面内每日记录提醒 |
| `reminder_time` | varchar(5) | 默认 `20:00` | 设备本地时间，格式 `HH:MM` |
| `high_risk` | boolean | 默认 false | 安全规则的硬拦截标记 |
| `screening_status` | varchar(32) | 默认 `pending` | `pending` / `eligible` / `needs_professional_review` |
| `screening_answers` | json | 默认 `{}` | 四项初筛布尔值，仅用于服务端安全判断 |
| `screened_at` | timestamptz nullable | 无 | 最近完成初筛时间 |
| `created_at` | timestamptz | UTC 当前时间 | 创建时间 |

## 3. `auth_sessions`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 会话 ID |
| `user_id` | varchar(36) | FK → `user_profiles.id`, index, cascade | 会话所属用户 |
| `token_hash` | varchar(64) | unique, index | SHA-256 令牌摘要；原始令牌不入库 |
| `expires_at` | timestamptz | index | 最长 72 小时内的过期时间 |
| `revoked_at` | timestamptz nullable | 无 | 注销时间；非空即失效 |
| `created_at` | timestamptz | UTC 当前时间 | 签发时间 |

## 4. `consent_records`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 授权记录 ID |
| `user_id` | varchar(36) | FK → `user_profiles.id`, index, cascade | 授权所属用户 |
| `version` | varchar(32) | 非空 | 用户接受的知情说明版本 |
| `status` | varchar(16) | check | `active` / `withdrawn` |
| `accepted_at` | timestamptz | UTC 当前时间 | 接受时间 |
| `withdrawn_at` | timestamptz nullable | 无 | 撤回时间 |

部分唯一索引 `uq_consent_active_user` 保证每名用户最多只有一条 `active` 授权；服务端只认可当前版本 `2026-09-20.v2`。

## 4.1 `food_safety_profiles`（V2 技术底座）

每名用户最多一条记录；不存在记录时，API 将六类状态都视为 `unknown`。`none` 必须由用户明确选择，不从空文本推断。

| 字段 | 类型 | 含义 |
|---|---|---|
| `user_id` | varchar(36), PK/FK | 档案所属用户；删除用户时级联删除 |
| `allergy_status`, `medication_status`, `condition_status`, `clinician_restriction_status` | varchar(16) | `unknown` / `none` / `present` |
| `allergens`, `medications`, `conditions`, `clinician_restrictions` | json 数组 | 仅在相应状态为 `present` 时保存具体合成条目 |
| `liver_kidney_status` | varchar(16) | 肝肾相关情况：`unknown` / `none` / `present` |
| `liver_kidney_conditions` | json 数组 | 仅在 `liver_kidney_status=present` 时保存具体合成条目 |
| `special_status` | varchar(24) | `unknown` / `none` / `pregnant` / `breastfeeding` / `other` |
| `special_details` | text | 仅在 `other` 时填写 |
| `updated_at` | timestamptz | 最近保存时间 |

`readiness` 是 API 动态计算的展示状态，不在表内持久化：信息缺失时为 `needs_information`；初筛或档案触发风险时为 `needs_professional_review`；全部明确回答且未触发上述条件时为 `awaiting_review_rules`。最后一种状态仍不允许生成正式食养方案。

## 4.2 `safety_rule_releases`

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | varchar(36), PK | 发布记录 ID |
| `version` | varchar(40), unique | 不可重复的规则版本 |
| `status` | varchar(16) | `published` / `retired`；部分唯一索引保证最多一个活动版本 |
| `evidence_ref` | varchar(240) | 外部签署或受控审核证据位置 |
| `reviewer_qualification` | varchar(160) | 审核人提交的资质说明；上线时须线下核验 |
| `reviewed_rule_codes` | json 数组 | 已明确审核的规则范围；必须覆盖服务端必需集合 |
| `attested` | boolean | 审核角色是否主动确认该记录 |
| `reviewer_id` | varchar(36) | 发布操作账号；不替代真实审核人签名 |
| `published_at`, `retired_at` | timestamptz | 发布和停用时间 |

发布、替换和停用均写入最小化审计；资质说明和证据正文不复制到审计 payload。没有活动版本时，安全决策保持 `awaiting_review_rules` 并阻断后续方案。

## 4.3 `evidence_sources`

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | varchar(36), PK | 来源版本 ID |
| `code`, `version` | varchar(64/40) | 组成唯一索引和稳定引用 `code@version` |
| `title`, `publisher` | varchar(240/160) | 来源标题与发布机构 |
| `url_or_archive_ref` | varchar(500) | 官方 URL 或受控归档位置 |
| `published_on` | date | 来源发布日期 |
| `jurisdiction` | varchar(80) | 适用地区或演示范围 |
| `content_hash` | varchar(64) | 登记内容的 SHA-256 标识 |
| `status` | varchar(20) | `active` / `superseded` / `withdrawn` |
| `checked_at`, `created_at` | timestamptz | 最近核验和创建时间 |

同一 `code + version` 唯一。把来源改为非活动状态前，服务层检查是否仍被当前发布条目引用；存在引用时拒绝操作。

## 4.4 `knowledge_items`

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | varchar(36), PK | 条目版本 ID |
| `content_type` | varchar(24) | `ingredient` / `recipe` / `contraindication` |
| `code`, `version` | varchar(64/40) | 业务代码和不可变版本；同类型、代码、版本唯一 |
| `title` | varchar(160) | 展示标题 |
| `payload` | json | 由对应 Pydantic Schema 校验的结构化内容 |
| `status` | varchar(20) | `draft` / `reviewed` / `published` / `retired` |
| `is_active` | boolean | 是否为同类型、同代码的当前生效发布版本 |
| `created_by` | varchar(36) | 创建账号或 `synthetic-seed` |
| `created_at`, `published_at`, `retired_at` | timestamptz | 生命周期时间 |

部分唯一索引 `uq_knowledge_items_active_version(content_type, code) WHERE is_active` 保证同时最多一个生效版本。食材 payload 保存物种、部位、类别、加工、过敏原、目录和来源；食谱保存精确食材版本、克数、步骤、替代、频次、周期、份量和注意事项；禁忌保存对象、触发条件、动作和提示。参与者目录只读取 `published + is_active`。

## 4.5 `content_reviews`

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | varchar(36), PK | 审核记录 ID |
| `item_id` | FK → `knowledge_items.id` | 被审核的不可变内容版本；删除条目时级联删除 |
| `decision` | varchar(16) | `approved` / `rejected` |
| `reviewer_id` | varchar(36) | 执行审核的登录账号 |
| `reviewer_qualification` | varchar(160) | 审核人声明的资质；正式上线须外部核验 |
| `review_scope` | varchar(240) | 本次核对的内容范围 |
| `evidence_ref` | varchar(240) | 签署、工单或受控证据位置 |
| `attested` | boolean | 审核员是否主动确认声明 |
| `notes` | text | 限制或修订说明，不复制到审计日志 |
| `created_at` | timestamptz | 审核时间 |

发布以按时间和 ID 排序的最新审核为准，必须为 `approved` 且 `attested=true`。已发布或已停用条目不可追加审核；修订须创建新版本。

## 5. `health_reports`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 报告标识 |
| `user_id` | varchar(36) | FK → `user_profiles.id`, index, cascade | 所属用户 |
| `filename` | varchar(255) | 非空 | 上传批次的原文件名，或手工批次的用户标题；正式日志不得记录该内容 |
| `institution` | varchar(120) | 默认空字符串 | 用户按报告原件核对的检测机构；空表示未填写 |
| `examined_at` | timestamptz nullable | 无 | 用户按报告原件核对的检查时间；与上传时间分开 |
| `source` | varchar(32) | 默认 `synthetic` | `synthetic`、`uploaded` 或用户逐项创建的 `manual` |
| `status` | varchar(32) | 默认 `needs_confirmation` | `processing` / `needs_confirmation` / `confirmed` / `ocr_failed` |
| `critical_marker_status` | varchar(16) | 默认 `unknown` | 用户对照报告原件确认的危急值标记：`unknown` / `no` / `yes`；不由数值或 OCR 自动推断 |
| `critical_marker_reviewed_at` | timestamptz nullable | 无 | 用户最近明确选择 `no` 或 `yes` 的时间；恢复 `unknown` 时清空 |
| `storage_provider` | varchar(32) | 非空 | `local_private`、无源文件的 `manual_entry`、未来的 `huawei_obs` 或种子/迁移来源 |
| `storage_key` | varchar(255) nullable | 无 | 私有随机对象键；API 不返回该字段 |
| `content_type` | varchar(64) | 非空 | 经签名校验的 PDF/PNG/JPEG MIME；手工批次为 `application/json` |
| `file_size` | integer | 默认 0 | 上传字节数，最大 5 MB |
| `content_sha256` | varchar(64) | 默认空字符串 | 文件内容摘要，不是公开下载标识 |
| `ocr_provider` | varchar(32) | 非空 | `mock_ocr`、不调用 OCR 的 `manual_entry`、真实适配器 `huawei_ocr` 或历史来源 |
| `ocr_status` | varchar(24) | 非空 | `processing` / `completed` / `failed` |
| `ocr_attempts` | integer | 默认 0 | 最近一次处理实际尝试次数 |
| `ocr_error_code` | varchar(64) nullable | 无 | 稳定失败类别，不保存外部服务响应正文 |
| `ocr_page_count` | integer | 默认 0 | OCR 返回页数 |
| `processed_at` | timestamptz nullable | 无 | 最近一次处理完成或失败时间 |
| `created_at` | timestamptz | UTC 当前时间 | 创建时间 |

组合索引 `idx_health_reports_user_created(user_id, created_at)` 支持“读取当前用户最近报告”的实际查询。

每次上传创建独立 `health_reports` 行，作为当前报告批次；历史列表按 `created_at`、`id` 降序分页。读取批次及详情均限制为当前参与者所有，不向列表暴露私有存储键。

## 6. `health_metrics`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 指标记录标识 |
| `report_id` | varchar(36) | FK → `health_reports.id`, index, cascade | 来源报告 |
| `user_id` | varchar(36) | FK → `user_profiles.id`, index, cascade | 所属用户 |
| `code` | varchar(64) | index | 标准指标代码 |
| `name` | varchar(80) | 非空 | 中文展示名 |
| `value` | float | 非空 | 结构化数值 |
| `unit` | varchar(32) | 非空 | 单位 |
| `reference_range` | varchar(64) | 默认空字符串 | 报告原参考范围 |
| `method` | varchar(120) | 默认空字符串 | 用户按原件核对的检测方法；用于可比性门禁，不用于诊断 |
| `flag` | varchar(16) | 默认 `normal` | `normal` / `attention`，不是疾病诊断 |
| `confirmed` | boolean | 默认 false | 是否经用户核对 |
| `review_status` | varchar(24) | 默认 `pending` | `pending` / `confirmed` / `corrected` |
| `raw_text` | text | 默认空字符串 | OCR 原文片段，或标明“手工录入”的输入摘要，用于用户核对 |
| `extracted_value` | float nullable | 无 | 首次标准化值，修正时保持不变 |
| `extracted_unit` | varchar(32) | 默认空字符串 | 首次标准化单位 |
| `extracted_reference_range` | varchar(64) | 默认空字符串 | 首次提取参考范围 |
| `confidence` | float | 默认 0 | OCR 候选置信度，应用层约束 0–1；手工输入固定为 1，但仍须用户确认 |
| `source_page` | integer | 默认 1 | 原文页码，从 1 开始 |
| `source_bbox` | json | 默认 `[0,0,1,1]` | `[x,y,width,height]` 归一化位置，单项 0–1 |
| `measured_at` | timestamptz | UTC 当前时间 | 测量或导入时间 |

报告只有在全部指标 `confirmed=true` 后才能转为 `confirmed`。唯一索引 `uq_health_metrics_report_code(report_id, code)` 防止同一报告用重复标准代码伪增指标数量；排序和实验服务按不同代码计数，并再次检查每条指标，避免绕过校对。

`unit_projection` 是 API 根据已确认的 `code`、`name`、`value` 和 `unit` 动态生成的派生字段，不入库。已知 P0 指标的名称或单位冲突会阻止报告最终确认；原 `value`、`unit`、`reference_range` 与 `extracted_*` 字段不被换算覆盖。投影规则版本为 `v2-unit-draft-1`，不能替代检测方法和参考范围可比性审核。

组合索引 `idx_health_metrics_report_name(report_id, name)` 支持报告指标列表的过滤与稳定排序。

## 7. `action_templates`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK | 模板 ID |
| `code` | varchar(64) | index | 稳定业务代码；允许保存多个历史版本 |
| `version` | varchar(32) | 与代码联合唯一 | 模板版本，如 `1.0.0` |
| `title` | varchar(120) | 非空 | 行动名称 |
| `category` | varchar(40) | 非空 | `activity` / `nutrition` |
| `description` | text | 非空 | 提醒日行为说明 |
| `evidence_summary` | text | 非空 | 依据摘要，不含疗效承诺 |
| `suitable_if` | text | 非空 | 适用条件 |
| `safety_note` | text | 非空 | 停止条件与安全边界 |
| `primary_metric` | varchar(120) | 非空 | 面向用户的主要观察指标 |
| `evidence_score` | float | 默认 0.7 | 排序输入，期望范围 0–1 |
| `effort_score` | float | 默认 0.5 | 执行负担，期望范围 0–1 |
| `observability_score` | float | 默认 0.8 | 短期可观测性，期望范围 0–1 |
| `risk_level` | varchar(20) | 默认 `low` | 只有 `low` 可进入自助实验 |
| `review_status` | varchar(32) | 默认 `draft` | `draft` / `prototype_approved` / `professionally_approved` / `retired` |
| `review_scope` | varchar(32) | 默认 `prototype_rules` | 明确审核范围，防止把产品规则校验冒充专业审核 |
| `reviewer_ref` | varchar(64) nullable | 无 | 审核角色或外部流程引用；合成种子使用 `synthetic-seed` |
| `reviewed_at` | timestamptz nullable | 无 | 最近审核时间 |
| `is_active` | boolean | 默认 false | 是否是该代码当前活动版本 |
| `deactivated_at` | timestamptz nullable | 无 | 最近停用时间 |
| `contraindication_codes` | json | 默认 `[]` | 与安全初筛布尔代码匹配的硬拦截条件 |
| `signal_metric_codes` | json | 默认 `[]` | 生成候选项至少需出现一个的已确认指标代码 |
| `ranking_policy_version` | varchar(32) | 默认 `rank-v1` | 排序公式版本 |
| `explanation_policy_version` | varchar(32) | 默认 `action-explain-v1` | 解释提示词与输出守卫版本 |

唯一索引 `uq_action_templates_code_version(code, version)` 保留历史版本；部分唯一索引 `uq_action_templates_active_code(code) WHERE is_active` 保证每个行动代码最多一个活动版本。原型审核角色不能写入 `professionally_approved`，Production 也不会发布 `prototype_approved`。

## 8. `experiments`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 实验 ID |
| `user_id` | varchar(36) | FK → `user_profiles.id`, index, cascade | 所属用户 |
| `action_id` | varchar(36) | FK → `action_templates.id`, index | 选定行动模板 |
| `status` | varchar(24) | 默认 `active`, check | `active` / `paused` / `terminated` / `completed` |
| `start_date` | date | 非空 | 第 1 天日期 |
| `end_date` | date | 非空 | 第 14 天日期，等于开始日期 + 13 天 |
| `randomization_seed` | integer | 非空 | 可复现实验日程的随机种子 |
| `schedule` | json | 非空 | 14 个 `{day,date,treatment,label}` 项 |
| `schedule_version` | varchar(32) | 默认 `balanced-14-v1` | 日程生成与校验规则版本 |
| `schedule_hash` | varchar(64) | 非空 | 版本、日期、种子和日程的 SHA-256 完整性摘要；API 不返回 |
| `schedule_locked_at` | timestamptz | 非空 | 日程锁定时间 |
| `started_at` | timestamptz | 非空 | 实验开始时间 |
| `paused_at` | timestamptz nullable | 无 | 最近暂停时间；恢复时清空，历史见审计事件 |
| `terminated_at` | timestamptz nullable | 无 | 终止时间；终止不可恢复 |
| `completed_at` | timestamptz nullable | 无 | 完成时间；完成不可恢复 |
| `next_step` | varchar(24) nullable | 无 | 最近选择的 `keep` / `adjust` / `extend` / `stop`；不自动改变实验状态 |
| `next_step_selected_at` | timestamptz nullable | 无 | 最近选择或改选时间 |
| `updated_at` | timestamptz | 非空 | 最近状态或记录变化时间 |
| `created_at` | timestamptz | UTC 当前时间 | 创建时间 |

业务约束：日程必须为连续 14 天且恰好 7 个提醒日；前端不能修改 `treatment`。检查约束 `ck_experiments_status` 限制状态集合；部分唯一索引 `uq_experiments_active_user(user_id) WHERE status='active'` 保证每名用户最多一个活动实验。组合索引 `idx_experiments_user_created(user_id, created_at)` 支持读取用户最近实验。创建新实验前服务层先暂停旧实验，唯一索引处理并发兜底。

## 9. `observations`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 观察记录 ID |
| `experiment_id` | varchar(36) | FK → `experiments.id`, index, cascade | 所属实验 |
| `observed_on` | date | 与实验 ID 组成唯一约束 | 记录日期 |
| `treatment` | boolean | 非空、由服务端日程决定 | true 为提醒日 |
| `completed` | boolean | 默认 false | 当天行动是否完成 |
| `steps_30m` | integer nullable | API 范围 0–20000 | 饭后 30 分钟步数 |
| `sleep_hours` | float nullable | API 范围 0–24 | 昨晚睡眠时长 |
| `sugary_drinks` | integer nullable | API 范围 0–20 | 含糖饮料次数 |
| `subjective_score` | integer nullable | API 范围 1–5 | 主观状态或餐后状态 |
| `missing_reason` | varchar(160) nullable | 固定枚举 | 忘记、设备不可用、身体不适、计划外事件或其他 |
| `discomfort_level` | varchar(16) | 默认 `none` | `none` / `mild` / `significant`；明显不适触发暂停 |
| `discomfort_details` | text nullable | API 最大 300 字符 | 身体不适的最小必要说明 |
| `unplanned_event` | text nullable | API 最大 300 字符 | 聚餐、出差等计划外干扰因素 |
| `notes` | text nullable | API 最大 500 字符 | 合成测试备注；正式日志不记录正文 |

唯一约束 `uq_experiment_day(experiment_id, observed_on)` 保证重复提交和重复导入更新同一天记录，而不是创建重复数据。审计事件只记录日期、格式及新增/更新计数，不记录不适说明、计划外事件或备注正文。

## 10. `audit_logs`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 审计事件 ID |
| `event_type` | varchar(80) | index | 如 `auth.demo_login`、`consent.accepted`、`profile.updated` |
| `actor_id` | varchar(36) | 默认 `system` | 操作者或系统标识 |
| `payload` | json | 默认 `{}` | 最小化业务 ID 与事件元数据 |
| `created_at` | timestamptz | UTC 当前时间, index | 事件时间 |

审计 payload 不得写入报告全文、密钥、请求头、联系方式或自由文本健康备注。`experiment.next_step_selected` 只保存 `experiment_id` 和选择代码。
