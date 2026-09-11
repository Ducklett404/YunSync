# YunSync API 契约草案

> 版本：V0.5
>
> 基础路径：`/api/v1`
>
> 在线契约：应用启动后访问 `/docs` 或 `/openapi.json`

## 1. 通用约定

- 请求与响应使用 UTF-8 JSON；文件上传使用 `multipart/form-data`。
- 日期采用 `YYYY-MM-DD`，时间采用带时区的 ISO 8601。
- 除登录、授权说明和系统健康检查外，请求必须携带 `Authorization: Bearer <demo token>`。
- 用户身份只从服务端会话解析；业务接口不接受客户端传入 `user_id`。
- 原始会话令牌只返回一次，数据库仅保存 SHA-256 摘要；Production 强制关闭演示登录。
- 每个响应返回 `X-Request-ID`。调用方可传入 1–64 位字母、数字、点、下划线或短横线；非法值由服务端替换。
- 未处理异常统一返回 `500 {"detail":"服务暂时不可用","request_id":"..."}`，日志不记录请求正文和敏感请求头。

## 2. 系统接口

| 方法 | 路径 | 成功响应 | 用途 |
|---|---|---|---|
| GET | `/healthz` | 200 `HealthStatus` | 进程存活检查，不访问数据库 |
| GET | `/readyz` | 200 `HealthStatus` | 数据库就绪检查 |

`HealthStatus`：`status`、`service`、`environment` 均为字符串。

## 3. 账号、授权与档案接口

| 方法 | 路径 | 权限 | 用途 |
|---|---|---|---|
| POST | `/api/v1/auth/demo` | 公开、仅非 Production | 登录 `demo-student` 或 `demo-reviewer`，签发短期令牌 |
| GET | `/api/v1/auth/me` | 已登录 | 读取当前会话用户 |
| POST | `/api/v1/auth/logout` | 已登录 | 吊销当前会话 |
| GET | `/api/v1/consents/notice` | 公开 | 读取当前知情说明版本与内容 |
| GET | `/api/v1/account/status` | 已登录 | 读取账号、授权与初筛状态 |
| POST | `/api/v1/consents/accept` | 参与者 | 接受指定的当前授权版本 |
| POST | `/api/v1/consents/withdraw` | 参与者 | 撤回授权并暂停活动实验 |
| GET/PATCH | `/api/v1/profile` | 参与者、有效授权 | 读取或更新合成健康档案 |
| POST | `/api/v1/profile/screening` | 参与者、有效授权 | 保存四项安全初筛；任一项触发即停止自助实验 |
| GET | `/api/v1/admin/audit-events` | 审核角色 | 返回最近 100 条最小化审计事件 |
| GET | `/api/v1/admin/action-templates` | 审核角色 | 读取全部模板版本及治理状态 |
| POST | `/api/v1/admin/action-templates/{id}/versions` | 审核角色 | 从已有模板复制一个不活动的草稿版本 |
| PATCH | `/api/v1/admin/action-templates/{id}/status` | 审核角色 | 设置草稿、原型规则通过或停用状态；切换活动版本 |

## 4. 健康业务接口

| 方法 | 路径 | 输入 | 成功响应 | 主要错误 |
|---|---|---|---|---|
| GET | `/api/v1/dashboard` | Bearer 会话 | 200 总览对象 | 401 未登录；403 未授权 |
| GET | `/api/v1/reports/latest` | Bearer 会话 | 200 `ReportAnalysis` | 403 未授权；404 无报告 |
| POST | `/api/v1/reports/analyze` | form `file` | 200 `ReportAnalysis` | 401 未登录；403 未授权；400 文件；503 存储/OCR |
| POST | `/api/v1/reports/{report_id}/retry` | path `report_id` | 200 `ReportAnalysis` | 409 状态不允许；503 存储/OCR |
| GET | `/api/v1/reports/{report_id}/source` | path `report_id` | 200 私有文件 | 404 不属于当前用户；503 文件不可用 |
| POST | `/api/v1/reports/{report_id}/metrics/{metric_id}/confirm` | path IDs | 200 `HealthMetric` | 404 对象不存在；409 OCR 未完成 |
| PATCH | `/api/v1/reports/{report_id}/metrics/{metric_id}` | `MetricCorrection` | 200 `HealthMetric` | 404 对象不存在；409 状态不允许；422 字段无效 |
| POST | `/api/v1/reports/{report_id}/confirm` | path `report_id` | 200 `ApiMessage` | 404 报告不存在；409 仍有字段未确认 |
| GET | `/api/v1/actions` | Bearer 会话 | 200 `Action[]` | 409 初筛未通过；未确认报告返回空数组 |
| POST | `/api/v1/experiments` | `ExperimentCreate` | 200 `Experiment` | 404 用户/模板；409 安全或确认条件未满足 |
| GET | `/api/v1/experiments/current` | Bearer 会话 | 200 `Experiment` | 403 未授权；404 无实验 |
| POST | `/api/v1/experiments/{id}/pause` | 无 | 200 `Experiment` | 404 实验；409 状态/日程冲突 |
| POST | `/api/v1/experiments/{id}/resume` | 无 | 200 `Experiment` | 404 实验；409 状态/单活动冲突 |
| POST | `/api/v1/experiments/{id}/terminate` | 无 | 200 `Experiment` | 404 实验；409 已进入终态 |
| POST | `/api/v1/experiments/{id}/complete` | 无 | 200 `Experiment` | 404 实验；409 周期或记录未完成 |
| POST | `/api/v1/experiments/{id}/observations` | `ObservationCreate` | 200 `ApiMessage` | 400 日期/分组/状态；404 实验 |
| GET | `/api/v1/experiments/{id}/result` | path `id` | 200 `ExperimentResult` | 404 实验/模板 |

所有路径参数对象均校验属于当前会话用户；其他用户的报告或实验统一返回 404。

`GET /actions` 只返回当前环境可发布的活动低风险模板。Development/Test 可使用 `prototype_approved`，Production 只接受 `professionally_approved`。同一行动代码最多一个活动版本。

## 5. 核心输入

### `MetricCorrection`

```json
{
  "name": "空腹血糖",
  "value": 6.3,
  "unit": "mmol/L",
  "reference_range": "3.9-6.1"
}
```

修正请求必须同时提交四个可编辑字段。成功后 `review_status` 为 `corrected`；原始 `raw_text`、`extracted_value`、`extracted_unit` 和 `extracted_reference_range` 保持不变。没有实际变化时按普通确认处理。

### `ReportAnalysis`

- 报告级状态：`status`、`ocr_status`、`ocr_attempts`、`ocr_error_code`、`ocr_provider`、`processed_at`；
- 非敏感存储元数据：`storage_provider`、`content_type`、`file_size`，不暴露内部对象键或磁盘路径；
- 每个指标包含结构化值、原始文本、0–1 置信度、从 1 开始的页码、四项归一化坐标及 `pending` / `confirmed` / `corrected` 校对状态；
- `ocr_status=failed` 时 `metrics` 必须为空。失败响应的 `detail` 包含 `message`、`report_id` 和稳定错误码，供页面恢复失败报告。

### `Action`

- `template_version`、`review_status`、`review_scope`、`review_label`：模板追溯信息；
- `score_components`：依据、可观察性和易执行性的权重与得分贡献，`total` 等于 `score`；
- `ranking_policy_version`：当前为 `rank-v1`；
- `explanation`、`explanation_source`、`explanation_policy_version`：受控解释、来源和守卫版本；
- `safety_checks`：报告确认、初筛、模板状态和低风险检查的用户可读记录。

`action-explain-v1` 拒绝诊断断言、调药建议、极端方案和疗效保证。Mock、真实 MaaS 或固定回退的来源必须明确标记，回退不得伪装成模型输出。

### `ExperimentCreate`

```json
{
  "action_id": "action-postmeal-walk",
  "start_date": "2026-09-10"
}
```

`start_date` 可省略，默认当天；创建即开始实验。日程与随机分组只由后端生成，新建时既有活动实验转为暂停。

### `Experiment`

- `status` / `status_label`：`active`（进行中）、`paused`（已暂停）、`terminated`（已终止）、`completed`（已完成）；
- `randomization_seed`、`schedule_version`、`schedule_locked_at`：日程审计信息；服务端另存不对外暴露的完整性摘要；
- `recorded_days` 与 `completed_days`：分别表示已提交记录和实际完成行动的天数，`progress` 与已记录天数一致；
- `allowed_transitions`：当前状态和完成条件下服务端允许的操作；
- `started_at`、`paused_at`、`terminated_at`、`completed_at`：状态时间戳；
- `schedule[].recorded` 表示该日期已有记录，`schedule[].completed` 表示当日行动完成。

完成实验要求当前日期不早于 `end_date`，且 14 个日程日期均已有记录。`terminated` 和 `completed` 均不可恢复。日程字段、7:7 分组或摘要不一致时返回 409 并停止读取、记录或状态转换。

### `ObservationCreate`

```json
{
  "observed_on": "2026-09-10",
  "completed": true,
  "steps_30m": 1200,
  "sleep_hours": 7.2,
  "subjective_score": 4,
  "missing_reason": null,
  "notes": "合成演示记录"
}
```

- `treatment` 仅用于检测前端篡改；省略时以后端日程为准，冲突时拒绝。
- `steps_30m`：0–20000；`sleep_hours`：0–24；`sugary_drinks`：0–20；`subjective_score`：1–5。
- 同一实验同一日期重复提交执行更新。

## 6. 结果契约

`ExperimentResult` 必须包含：

- `metric_code`、`metric_label`、`metric_unit`、`improvement_direction`；
- 提醒日与常规日有效天数及均值；
- `observed_difference`、`completion_rate`；
- `status`、中性 `message` 和 `caveats`。

提醒日或常规日任一组少于 2 个有效观测时，均值与差异为 `null`，不得返回方向性健康结论。

## 7. 错误状态码

| 状态码 | 场景 |
|---:|---|
| 400 | 文件、日期、实验状态或分组不符合业务规则 |
| 401 | 缺少、过期或已吊销的演示会话 |
| 403 | 未接受当前授权版本或角色权限不足 |
| 404 | 用户、报告、实验或模板不存在 |
| 409 | 安全拦截、报告未确认或其他业务前置条件冲突 |
| 422 | Pydantic 请求结构或字段范围校验失败 |
| 500 | 未处理错误，返回通用信息与 request ID |
| 503 | OCR 等外部依赖暂时不可用 |
