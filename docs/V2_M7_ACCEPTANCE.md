# M7 系统联调、安全与真实测试验收单

> 工程门禁：已完成云适配器、失败关闭策略、安全与模型评测自动化实现
> 正式里程碑：等待真实云联调、5—10 名测试者记录、专业内容复核和负责人签署

## 1. 工程交付

- [x] PostgreSQL psycopg、Redis/DCS、最小化 JSON 日志及生产配置门禁保持可用。
- [x] OBS 使用官方 Python SDK 完成私有对象上传与内存读取；对象键随机生成并限制用户段、后缀和读取格式，环境凭据及 ECS 实例身份均有契约测试。
- [x] OCR 使用华为云 SDK 调用智能文档解析，只提取可人工核对的 P0 指标；冲突、空结果、无效载荷和服务失败关闭失败。
- [x] MaaS 使用 Bearer API Key 调用配置的 V2 Chat Completions 端点，固定模型、零温度、白名单上下文和 JSON 输出；HTTP、超时、结构或安全校验失败时回退到固定文案。
- [x] `cloud-preflight-v4` 分开报告代码实现与真实验收，且不输出连接串、凭据或验收编号。
- [x] 权限、越权、上传签名与路径、日志脱敏、提示词注入、诊断/调药/疗效越界、无依据数值和目录外材料自动化测试已纳入回归。

## 2. 自动化证据

| 范围 | 证据 |
|---|---|
| OBS/OCR/MaaS 契约 | `tests/test_huawei_obs_contract.py`、`tests/test_huawei_ocr_contract.py`、`tests/test_huawei_maas_contract.py` |
| 云配置与真实验收门禁 | `tests/test_config.py`、`tests/test_cloud_readiness.py` |
| 身份、角色、对象归属与上传 | `tests/test_api.py`、`tests/test_report_batches.py`、`tests/test_http_security.py` |
| 模型结构、幻觉与越界 | `tests/test_m7_model_safety.py`、`tests/test_action_policy.py`、`tests/test_result_analysis.py` |
| 发布目录与目录外材料 | `tests/test_content_knowledge.py`、`tests/test_care_plan_service.py` |

本地测试只使用合成数据、假传输和假 OBS 客户端，不是 RDS、OBS、OCR、MaaS 或云日志平台的成功调用证据。

## 3. 当前缺陷结论

- 自动化覆盖范围内没有未关闭的 P0/P1 失败项。
- 上述结论不覆盖真实网络、IAM 策略、桶策略、模型版本差异、真实版式识别效果或真人可用性问题。
- 真实阶段发现的任何 P0/P1 必须登记、修复和复测后才能签署本单。

## 4. 正式验收待办

- [ ] 按 `V2_M7_QA_RUNBOOK.md` 完成 RDS、DCS、OBS、OCR、MaaS 和云日志服务联调，保存脱敏记录；将三项提供方记录编号注入预检配置。
- [ ] 邀请 5—10 名符合目标人群且已知情的测试者完成主流程，记录完成率、阻断点、严重缺陷和结论。
- [ ] 临床营养、中医药及法规/内容负责人按职责复核全部用户可见健康内容与安全边界。
- [ ] QA 确认真实阶段 P0/P1 均关闭，项目负责人签署。

| 角色 | 姓名/组织 | 结论 | 证据位置 | 日期 |
|---|---|---|---|---|
| 云平台联调负责人 | 待填写 | 待确认 |  |  |
| QA 负责人 | 待填写 | 待确认 |  |  |
| 5—10 名测试者记录汇总人 | 待填写 | 待确认 |  |  |
| 临床营养审核人 | 待填写 | 待确认 |  |  |
| 中医药内容审核人 | 待填写 | 待确认 |  |  |
| 法规/内容负责人 | 待填写 | 待确认 |  |  |
| 项目负责人 | 待填写 | 待确认 |  |  |
