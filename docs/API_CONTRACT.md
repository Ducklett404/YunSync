# YunSync API 契约草案

> 版本：V0.1
>
> 基础路径：`/api/v1`
>
> 在线契约：应用启动后访问 `/docs` 或 `/openapi.json`

## 1. 通用约定

- 请求与响应使用 UTF-8 JSON；文件上传使用 `multipart/form-data`。
- 日期采用 `YYYY-MM-DD`，时间采用带时区的 ISO 8601。
- 当前默认用户为合成账号 `demo-user`，正式身份认证在第 3 周实现。
- 每个响应返回 `X-Request-ID`。调用方可传入 1–64 位字母、数字、点、下划线或短横线；非法值由服务端替换。
- 未处理异常统一返回 `500 {"detail":"服务暂时不可用","request_id":"..."}`，日志不记录请求正文和敏感请求头。

## 2. 系统接口

| 方法 | 路径 | 成功响应 | 用途 |
|---|---|---|---|
| GET | `/healthz` | 200 `HealthStatus` | 进程存活检查，不访问数据库 |
| GET | `/readyz` | 200 `HealthStatus` | 数据库就绪检查 |

`HealthStatus`：`status`、`service`、`environment` 均为字符串。

## 3. 业务接口

| 方法 | 路径 | 输入 | 成功响应 | 主要错误 |
|---|---|---|---|---|
| GET | `/api/v1/dashboard` | query `user_id` 可选 | 200 总览对象 | 当前无用户时返回空对象 |
| GET | `/api/v1/reports/latest` | query `user_id` 可选 | 200 `ReportAnalysis` | 404 无报告 |
| POST | `/api/v1/reports/analyze` | query `user_id`；form `file` | 200 `ReportAnalysis` | 400 文件校验；404 用户；503 OCR |
| POST | `/api/v1/reports/{report_id}/confirm` | path `report_id` | 200 `ApiMessage` | 404 报告不存在 |
| GET | `/api/v1/actions` | query `user_id` 可选 | 200 `Action[]` | 404 用户不存在；未确认/高风险返回空数组 |
| POST | `/api/v1/experiments` | `ExperimentCreate` | 200 `Experiment` | 404 用户/模板；409 安全或确认条件未满足 |
| GET | `/api/v1/experiments/current` | query `user_id` 可选 | 200 `Experiment` | 404 无实验 |
| POST | `/api/v1/experiments/{id}/observations` | `ObservationCreate` | 200 `ApiMessage` | 400 日期/分组/状态；404 实验 |
| GET | `/api/v1/experiments/{id}/result` | path `id` | 200 `ExperimentResult` | 404 实验/模板 |

## 4. 核心输入

### `ExperimentCreate`

```json
{
  "user_id": "demo-user",
  "action_id": "action-postmeal-walk",
  "start_date": "2026-09-10"
}
```

`start_date` 可省略，默认当天；日程与随机分组只由后端生成。

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

## 5. 结果契约

`ExperimentResult` 必须包含：

- `metric_code`、`metric_label`、`metric_unit`、`improvement_direction`；
- 提醒日与常规日有效天数及均值；
- `observed_difference`、`completion_rate`；
- `status`、中性 `message` 和 `caveats`。

提醒日或常规日任一组少于 2 个有效观测时，均值与差异为 `null`，不得返回方向性健康结论。

## 6. 错误状态码

| 状态码 | 场景 |
|---:|---|
| 400 | 文件、日期、实验状态或分组不符合业务规则 |
| 404 | 用户、报告、实验或模板不存在 |
| 409 | 安全拦截、报告未确认或其他业务前置条件冲突 |
| 422 | Pydantic 请求结构或字段范围校验失败 |
| 500 | 未处理错误，返回通用信息与 request ID |
| 503 | OCR 等外部依赖暂时不可用 |
