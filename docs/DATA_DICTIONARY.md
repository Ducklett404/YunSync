# YunSync 数据字典

> 版本：V0.1
>
> 对应迁移：`6169c3448442_initial_schema`
>
> 数据口径：开发与演示环境只保存合成数据

## 1. 关系总览

```text
user_profiles 1 ── N health_reports 1 ── N health_metrics
       │
       └─────── 1 ── N experiments N ── 1 action_templates
                           │
                           └──── 1 ── N observations

audit_logs：独立审计事件表，通过 actor_id 与 payload 中的业务 ID 追踪操作。
```

删除用户时，报告、指标、实验和观察记录通过外键级联删除；行动模板和审计日志不随用户级联删除。正式环境的删除与保留政策须在授权模块完成后再次评审。

## 2. `user_profiles`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK | 演示用户标识；当前固定为 `demo-user` |
| `nickname` | varchar(80) | 默认“演示用户” | 展示昵称，不应存真实姓名 |
| `age_range` | varchar(20) | 默认 `25-34` | 年龄段，不保存精确出生日期 |
| `goal` | varchar(120) | 默认“改善日常活动习惯” | 健康行为目标 |
| `high_risk` | boolean | 默认 false | 安全规则的硬拦截标记 |
| `created_at` | timestamptz | UTC 当前时间 | 创建时间 |

## 3. `health_reports`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 报告标识 |
| `user_id` | varchar(36) | FK → `user_profiles.id`, index, cascade | 所属用户 |
| `filename` | varchar(255) | 非空 | 原文件名；正式日志不得记录文件内容 |
| `source` | varchar(32) | 默认 `synthetic` | `synthetic` 或未来的 `uploaded` |
| `status` | varchar(32) | 默认 `needs_confirmation` | `needs_confirmation` / `confirmed` |
| `created_at` | timestamptz | UTC 当前时间 | 创建时间 |

## 4. `health_metrics`

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
| `measured_at` | timestamptz | UTC 当前时间 | 测量或导入时间 |

## 5. `action_templates`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK | 模板 ID |
| `code` | varchar(64) | unique, index | 稳定业务代码 |
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

模板审核状态与版本字段计划在第 5 周迁移中补充，现有表仅用于可行性验证。

## 6. `experiments`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 实验 ID |
| `user_id` | varchar(36) | FK → `user_profiles.id`, index, cascade | 所属用户 |
| `action_id` | varchar(36) | FK → `action_templates.id`, index | 选定行动模板 |
| `status` | varchar(24) | 默认 `active` | `active` / `paused`，后续增加完整状态机 |
| `start_date` | date | 非空 | 第 1 天日期 |
| `end_date` | date | 非空 | 第 14 天日期，等于开始日期 + 13 天 |
| `randomization_seed` | integer | 非空 | 可复现实验日程的随机种子 |
| `schedule` | json | 非空 | 14 个 `{day,date,treatment,label}` 项 |
| `created_at` | timestamptz | UTC 当前时间 | 创建时间 |

业务约束：日程必须为 14 天且恰好 7 个提醒日；前端不能修改 `treatment`。单用户单活动实验当前由服务层通过暂停旧实验实现，数据库级约束在第 6 周评审。

## 7. `observations`

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
| `missing_reason` | varchar(160) nullable | 最大 160 字符 | 缺失原因 |
| `notes` | text nullable | API 最大 500 字符 | 合成测试备注；正式日志不记录正文 |

唯一约束 `uq_experiment_day(experiment_id, observed_on)` 保证重复提交更新同一天记录，而不是创建重复数据。

## 8. `audit_logs`

| 字段 | 类型 | 约束/默认值 | 含义 |
|---|---|---|---|
| `id` | varchar(36) | PK, UUID | 审计事件 ID |
| `event_type` | varchar(80) | index | 如 `report.mock_analyzed`、`experiment.created`、`observation.saved` |
| `actor_id` | varchar(36) | 默认 `system` | 操作者或系统标识 |
| `payload` | json | 默认 `{}` | 最小化业务 ID 与事件元数据 |
| `created_at` | timestamptz | UTC 当前时间, index | 事件时间 |

审计 payload 不得写入报告全文、密钥、请求头、联系方式或自由文本健康备注。
