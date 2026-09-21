# YunSync API 契约草案

> 版本：V0.9
>
> 基础路径：`/api/v1`
>
> 在线契约：非 Production 环境启动后访问 `/docs` 或 `/openapi.json`

## 1. 通用约定

- 请求与响应使用 UTF-8 JSON；文件上传使用 `multipart/form-data`。
- 日期采用 `YYYY-MM-DD`，时间采用带时区的 ISO 8601。
- 除登录、授权说明和系统健康检查外，请求必须携带 `Authorization: Bearer <demo token>`。
- 用户身份只从服务端会话解析；业务接口不接受客户端传入 `user_id`。
- 原始会话令牌只返回一次，数据库仅保存 SHA-256 摘要；Production 强制关闭演示登录。
- 每个响应返回 `X-Request-ID`。调用方可传入 1–64 位字母、数字、点、下划线或短横线；非法值由服务端替换。
- 未处理异常统一返回 `500 {"detail":"服务暂时不可用","request_id":"..."}`，日志不记录请求正文和敏感请求头。
- API 响应携带安全响应头和 `Cache-Control: no-store`；启用限流后返回 `X-RateLimit-Limit`、`X-RateLimit-Remaining`，超限返回 429 与 `Retry-After`。
- Production 关闭交互式 API 文档，并要求 HTTPS、可信 Host 与受限反向代理来源。

## 2. 系统接口

| 方法 | 路径 | 成功响应 | 用途 |
|---|---|---|---|
| GET | `/healthz` | 200 `HealthStatus` | 进程存活检查，不访问数据库 |
| GET | `/readyz` | 200 `HealthStatus` | 数据库就绪检查；可选缓存故障时保持就绪并标记降级 |

`HealthStatus`：`status`、`service`、`environment`，以及可选 `dependencies` 和 `degraded`。`/readyz` 的 `dependencies.database` 为 `ready`；缓存为 `disabled`、`redis` 或 `memory_fallback`。缓存不是核心就绪依赖，Redis/DCS 不可用时返回 200、`degraded=true`。

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
| GET/PATCH | `/api/v1/profile/food-safety` | 参与者、有效授权 | 读取或保存过敏、用药、疾病、肝肾情况、饮食限制及特殊状态；未回答默认 `unknown` |
| GET | `/api/v1/safety/decision` | 参与者、有效授权 | 返回 A/B/C 或资料/规则待办、待补项目和已发布规则版本 |
| POST | `/api/v1/profile/screening` | 参与者、有效授权 | 保存四项安全初筛；任一项触发即停止自助实验 |
| GET | `/api/v1/admin/audit-events` | 审核角色 | 返回最近 100 条最小化审计事件 |
| GET | `/api/v1/admin/action-templates` | 审核角色 | 读取全部模板版本及治理状态 |
| POST | `/api/v1/admin/action-templates/{id}/versions` | 审核角色 | 从已有模板复制一个不活动的草稿版本 |
| PATCH | `/api/v1/admin/action-templates/{id}/status` | 审核角色 | 设置草稿、原型规则通过或停用状态；切换活动版本 |
| GET | `/api/v1/admin/safety-rules` | 审核角色 | 读取安全规则发布和停用历史 |
| POST | `/api/v1/admin/safety-rules` | 审核角色 | 登记完整审核范围、证据与资质说明并发布新版本；自动停用旧活动版本 |
| PATCH | `/api/v1/admin/safety-rules/{id}/retire` | 审核角色 | 停用活动版本，使 A 层即时关闭 |

食养安全档案的 PATCH 请求须包含过敏、用药、疾病、肝肾情况、医生限制和特殊状态六类状态；状态为 `present` 时须提供对应的非空条目列表。响应的 `readiness` 只表示资料状态或需专业评估。审计只记录变更字段名和资料状态，不记录具体过敏、疾病或用药内容。

安全规则发布请求的 `attested` 必须为 `true`，并覆盖服务端规定的全部规则代码。发布接口只保存工作流记录，不验证审核人的执业资质真伪；上线验收必须核对 `evidence_ref` 和实际审核人。A 层只表示可进入后续已审核内容候选流程，不代表已生成食养方案。

## 4. 健康业务接口

| 方法 | 路径 | 输入 | 成功响应 | 主要错误 |
|---|---|---|---|---|
| GET | `/api/v1/dashboard` | Bearer 会话 | 200 总览对象 | 401 未登录；403 未授权 |
| GET | `/api/v1/reports/latest` | Bearer 会话 | 200 `ReportAnalysis` | 403 未授权；404 无报告 |
| GET | `/api/v1/reports?limit=20&offset=0` | `limit` 1–100；`offset` ≥0 | 200 `ReportList` | 403 未授权；422 分页参数无效 |
| GET | `/api/v1/reports/{report_id}` | path `report_id` | 200 `ReportAnalysis` | 404 报告不存在或不属于当前用户 |
| POST | `/api/v1/reports/manual` | `ManualReport` | 200 `ReportAnalysis` | 400 重复标准指标；403 未授权；422 字段无效 |
| PATCH | `/api/v1/reports/{report_id}/metadata` | 检查日期、检测机构 | 200 `ReportAnalysis` | 404 报告不存在；422 日期或字段无效 |
| GET | `/api/v1/metrics/summary?report_limit=20` | `report_limit` 1–50 | 200 `MetricHistory` | 403 未授权；422 参数无效 |
| POST | `/api/v1/reports/analyze` | form `file` | 200 `ReportAnalysis` | 401 未登录；403 未授权；400 文件；503 存储/OCR |
| POST | `/api/v1/reports/{report_id}/retry` | path `report_id` | 200 `ReportAnalysis` | 409 状态不允许；503 存储/OCR |
| PATCH | `/api/v1/reports/{report_id}/critical-marker` | `{ "status": "unknown|no|yes" }` | 200 `ReportAnalysis` | 404 报告不存在或不属于当前用户；422 状态无效 |
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
| GET | `/api/v1/experiments/{id}/observations/template?format=csv|json` | Bearer 会话 | CSV/JSON 附件 | 404 实验；409 日程损坏 |
| POST | `/api/v1/experiments/{id}/observations/import` | `ObservationImport` | 200 `ObservationImportResult` | 400 文件、日期、指标或状态错误 |
| GET | `/api/v1/experiments/{id}/result` | path `id` | 200 `ExperimentResult` | 404 实验/模板 |
| GET | `/api/v1/experiments/{id}/export` | path `id` | JSON 附件 | 403 未授权；404 实验；409 日程损坏 |
| POST | `/api/v1/experiments/{id}/next-step` | `{ "code": "keep|adjust|extend|stop" }` | 200 `NextStepChoice` | 404 实验；422 代码无效 |

所有路径参数对象均校验属于当前会话用户；其他用户的报告或实验统一返回 404。

`ReportList` 返回 `items`、`total`、`limit`、`offset`。每项仅含报告 ID、文件名、状态、OCR 状态、用户确认的危急标记状态和创建时间；按创建时间、ID 降序排列。该接口用于切换已上传的报告批次。安全分流只以最新报告为准。

`MetricHistory` 仅读取当前用户最近 `report_limit` 份**整份已确认**报告中的逐项已确认 P0 指标。已填写检查日期的记录按检查日期排序；缺少日期的历史记录排在已知日期之前。按标准代码合并别名，保留报告 ID、检查日期、机构、检测方法、原值、原单位、参考范围和单位投影。只有标准指标唯一、单位可投影、检查日期明确、两次检测方法填写并一致，且参考范围填写并经文本规范化后一致时，`latest_pair` 才返回标准单位下的算术差和方向。检测方法缺失或变化、参考范围缺失或不同、单位无法投影、同批次重复指标时差值为 `null`；机构和原单位变化以限制说明返回。参考范围规范化仅统一空白和常见标点写法，不推断区间的医学等价性。算术差不得被解释为临床趋势或食养效果。未知代码不进入此接口。历史规则版本为 `v2-history-draft-3`。

### `ManualReport`

手工批次包含 1—30 个指标、批次名称、带时区的检查时间和可选检测机构。每项包含名称、数值、单位、可选参考范围、可选检测方法和可选标准代码；普通用户页面不要求填写标准代码，后端按名称别名匹配，未知名称生成稳定的 `manual_*` 内部代码并保留原名称。同一批次映射到相同标准代码的重复项会整体拒绝。创建后所有指标仍为 `pending`，必须走逐项确认和报告最终确认；手工批次没有可下载源文件，源文件接口返回 409。

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

修正请求必须同时提交名称、数值、单位和参考范围，并可提交检测方法。成功后 `review_status` 为 `corrected`；原始 `raw_text`、`extracted_value`、`extracted_unit` 和 `extracted_reference_range` 保持不变。没有实际变化时按普通确认处理。整份报告确认后只能补充或更正检测方法，不能借此同时改变已锁定数值；单位/名称冲突的受限恢复路径除外。

### `ReportAnalysis`

- 报告级状态：`status`、`ocr_status`、`ocr_attempts`、`ocr_error_code`、`ocr_provider`、`processed_at`；
- 检查元数据：`examined_at`、`institution`；指标另含用户核对的 `method`。修改已确认报告的检查元数据或检测方法会将报告恢复为待确认状态，并记录不含具体内容的审计事件；
- 用户对照原件确认的 `critical_marker_status`（`unknown` / `no` / `yes`）及 `critical_marker_reviewed_at`。默认 `unknown`；`yes` 触发初步 C 层安全提示，系统不从 OCR 数值或颜色推断危急值；
- 非敏感存储元数据：`storage_provider`、`source_available`、`content_type`、`file_size`，不暴露内部对象键或磁盘路径；`source_available=false` 时前端不请求或展示源文件预览；
- 每个指标包含结构化值、原始文本、0–1 置信度、从 1 开始的页码、四项归一化坐标及 `pending` / `confirmed` / `corrected` 校对状态；
- 每个指标的 `unit_projection` 在读取时按 `v2-unit-draft-1` 计算，包含 `status`、`standard_unit`、`standard_value`、`rule_version`。未确认、未知指标、名称冲突或不支持的单位不返回标准数值；原 `value`、`unit`、`reference_range` 和首次提取字段保持不变；
- `ocr_status=failed` 时 `metrics` 必须为空。失败响应的 `detail` 包含 `message`、`report_id` 和稳定错误码，供页面恢复失败报告。

关闭 Mock 后，华为云适配器按智能文档解析接口逐页提交 PDF，PNG/JPEG 提交一页；默认最多处理 10 页，可用 `OCR_PDF_MAX_PAGES` 在 1–20 页内配置。适配器只接收能映射到 P0 名称且表格行中具有明确数值和单位的候选，保留置信度和位置，其余内容交给人工录入或修正。真实云调用仍须凭证、服务开通和脱敏样本验收。

已逐项确认的字段在报告最终确认前仍可修正。标准 P0 指标若有名称冲突或未支持的单位，`POST /reports/{report_id}/confirm` 返回 409；未知的非 P0 指标不参与单位投影，也不因缺少单位规则阻止报告确认。单位投影不代表跨实验室可比性已通过审核。
对历史上已经确认、但现行单位规则判定有冲突的报告，仅冲突字段可重新修正；首次修正会将报告恢复为 `needs_confirmation`，须重新完成报告确认，并记录最小化审计事件。

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
- `next_step`、`next_step_selected_at`：最近一次复盘选择及时间；未选择时为 `null`；
- `schedule[].recorded` 表示该日期已有记录，`schedule[].completed` 表示当日行动完成；`schedule[].observation` 返回所属用户已有记录详情，便于安全回填修改。

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
  "discomfort_level": "none",
  "discomfort_details": null,
  "unplanned_event": null,
  "notes": "合成演示记录"
}
```

- `treatment` 仅用于检测前端篡改；省略时以后端日程为准，冲突时拒绝。
- `steps_30m`：0–20000；`sleep_hours`：0–24；`sugary_drinks`：0–20；`subjective_score`：1–5。
- 行动主要指标固定为：饭后活动 `steps_30m`、饮料替换 `sugary_drinks`、进食顺序 `subjective_score`；提交不属于当前行动的主要指标字段时拒绝。
- `missing_reason` 仅允许 `forgot`、`device_unavailable`、`physical_discomfort`、`unplanned_event`、`other`；主要指标为空时必填。
- `discomfort_level` 为 `none`、`mild` 或 `significant`；后两者需要简要说明，`significant` 会在保存后自动暂停实验。
- 同一实验同一日期重复提交执行更新。

### `ObservationImport`

```json
{
  "format": "csv",
  "content": "observed_on,completed,steps_30m,discomfort_level\\n2026-09-10,true,1200,none\\n"
}
```

- `content` 最大 200,000 字符，单次 1–14 条；JSON 可使用数组或 `{ "records": [...] }`。
- 当前文件中的全部记录先完成格式、周期、未来日期、行动指标与日程校验，再在一个事务中按日期新增或更新。
- 响应返回 `imported_days`、`created_days` 和 `updated_days`；重复上传同一文件不会产生重复日期记录。

## 6. 结果契约

`ExperimentResult` 必须包含：

- `metric_code`、`metric_label`、`metric_unit`、`improvement_direction`；
- 提醒日与常规日有效天数、均值与中位数；
- `observed_difference`、`completion_rate`、`effective_rate`、`valid_days`、`missing_days` 和按原因汇总的 `missing_reason_counts`；
- `bootstrap_ci_lower`、`bootstrap_ci_upper` 和固定为 2,000 的 `bootstrap_iterations`；
- `outlier_count`、`outlier_days`、保留原值的每日 `analysis_points` 与可选 `sensitivity_difference`；
- `status`、中性 `message`、`caveats`、`analysis_version`；
- `explanation`、`explanation_source`、`explanation_policy_version`；
- `recommended_next_step` 和四项 `next_step_options`，每项包含建议与当前选中状态。

主要分析使用所有非空主要指标值，独立于行动是否完成；完成率与有效率分别统计。提醒日或常规日任一组少于 2 个有效观测时，均值、中位数、差异和区间均为 `null`，不得返回方向性健康结论。AI 或 Mock 解释超时、报错或未通过 `result-explain-v1` 守卫时，`explanation_source` 为 `policy_fallback`。

`NextStepChoice` 返回 `experiment_id`、`code` 和 `selected_at`。重复提交覆盖最近选择并新增最小化审计事件，不自动新建、停止或改变实验状态。

`GET /experiments/{id}/export` 返回 `yunsync-experiment-export-v1` JSON 附件，包含导出时间、非诊疗声明、锁定实验快照、逐日记录和当前结果复盘。响应使用 `Cache-Control: private, no-store`，且仅实验所属参与者可以下载。

## 7. 错误状态码

| 状态码 | 场景 |
|---:|---|
| 400 | 文件、日期、实验状态或分组不符合业务规则 |
| 401 | 缺少、过期或已吊销的演示会话 |
| 403 | 未接受当前授权版本或角色权限不足 |
| 404 | 用户、报告、实验或模板不存在 |
| 409 | 安全拦截、报告未确认或其他业务前置条件冲突 |
| 422 | Pydantic 请求结构或字段范围校验失败 |
| 429 | 超过当前进程或上游网关的请求频率限制 |
| 500 | 未处理错误，返回通用信息与 request ID |
| 503 | OCR 等外部依赖暂时不可用 |
