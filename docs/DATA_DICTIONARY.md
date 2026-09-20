# YunSync 数据字典

> 版本：V0.9（含 V2 食养安全档案及报告危急标记）
>
> 对应迁移：`6169c3448442_initial_schema`、`8c1d2e3f4a5b_identity_consent_profile`、`a4b5c6d7e8f9_report_ocr_review`、`b5c6d7e8f9a0_action_template_governance`、`c6d7e8f9a0b1_experiment_state_machine`、`d7e8f9a0b1c2_daily_record_support`、`e8f9a0b1c2d3_result_review_choice`、`f9a0b1c2d3e4_performance_indexes`、`0a1b2c3d4e5f_unique_report_metric_codes`、`b1c2d3e4f5a6_food_safety_profile`、`c2d3e4f5a6b7_report_critical_marker`
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
```

删除用户时，会话、授权、报告、指标、食养安全档案、实验和观察记录通过外键级联删除；行动模板和审计日志不随用户级联删除。审计日志只保存最小事件元数据，不保存会话令牌、文件名、档案正文、食养风险详情或初筛答案。

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

每名用户最多一条记录；不存在记录时，API 将五类状态都视为 `unknown`。`none` 必须由用户明确选择，不从空文本推断。

| 字段 | 类型 | 含义 |
|---|---|---|
| `user_id` | varchar(36), PK/FK | 档案所属用户；删除用户时级联删除 |
| `allergy_status`, `medication_status`, `condition_status`, `clinician_restriction_status` | varchar(16) | `unknown` / `none` / `present` |
| `allergens`, `medications`, `conditions`, `clinician_restrictions` | json 数组 | 仅在相应状态为 `present` 时保存具体合成条目 |
| `special_status` | varchar(24) | `unknown` / `none` / `pregnant` / `breastfeeding` / `other` |
| `special_details` | text | 仅在 `other` 时填写 |
| `updated_at` | timestamptz | 最近保存时间 |

`readiness` 是 API 动态计算的展示状态，不在表内持久化：信息缺失时为 `needs_information`；初筛或档案触发风险时为 `needs_professional_review`；全部明确回答且未触发上述条件时为 `awaiting_review_rules`。最后一种状态仍不允许生成正式食养方案。

## 5. `health_reports`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 报告标识 |
| `user_id` | varchar(36) | FK → `user_profiles.id`, index, cascade | 所属用户 |
| `filename` | varchar(255) | 非空 | 原文件名；正式日志不得记录文件内容 |
| `source` | varchar(32) | 默认 `synthetic` | `synthetic` 或未来的 `uploaded` |
| `status` | varchar(32) | 默认 `needs_confirmation` | `processing` / `needs_confirmation` / `confirmed` / `ocr_failed` |
| `critical_marker_status` | varchar(16) | 默认 `unknown` | 用户对照报告原件确认的危急值标记：`unknown` / `no` / `yes`；不由数值或 OCR 自动推断 |
| `critical_marker_reviewed_at` | timestamptz nullable | 无 | 用户最近明确选择 `no` 或 `yes` 的时间；恢复 `unknown` 时清空 |
| `storage_provider` | varchar(32) | 非空 | `local_private`、未来的 `huawei_obs` 或种子/迁移来源 |
| `storage_key` | varchar(255) nullable | 无 | 私有随机对象键；API 不返回该字段 |
| `content_type` | varchar(64) | 非空 | 经签名校验的 PDF/PNG/JPEG MIME |
| `file_size` | integer | 默认 0 | 上传字节数，最大 5 MB |
| `content_sha256` | varchar(64) | 默认空字符串 | 文件内容摘要，不是公开下载标识 |
| `ocr_provider` | varchar(32) | 非空 | `mock_ocr`、未来的 `huawei_ocr` 或历史来源 |
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
| `flag` | varchar(16) | 默认 `normal` | `normal` / `attention`，不是疾病诊断 |
| `confirmed` | boolean | 默认 false | 是否经用户核对 |
| `review_status` | varchar(24) | 默认 `pending` | `pending` / `confirmed` / `corrected` |
| `raw_text` | text | 默认空字符串 | OCR 原文片段，用于用户核对 |
| `extracted_value` | float nullable | 无 | 首次标准化值，修正时保持不变 |
| `extracted_unit` | varchar(32) | 默认空字符串 | 首次标准化单位 |
| `extracted_reference_range` | varchar(64) | 默认空字符串 | 首次提取参考范围 |
| `confidence` | float | 默认 0 | OCR 候选置信度，应用层约束 0–1 |
| `source_page` | integer | 默认 1 | 原文页码，从 1 开始 |
| `source_bbox` | json | 默认 `[0,0,1,1]` | `[x,y,width,height]` 归一化位置，单项 0–1 |
| `measured_at` | timestamptz | UTC 当前时间 | 测量或导入时间 |

报告只有在全部指标 `confirmed=true` 后才能转为 `confirmed`。唯一索引 `uq_health_metrics_report_code(report_id, code)` 防止同一报告用重复标准代码伪增指标数量；排序和实验服务按不同代码计数，并再次检查每条指标，避免绕过校对。

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
