# V2 专业内容数据字典 Schema

> Schema 版本：`v2-content-schema-1`
> 状态：字段框架已建立；M4 导入的每一条真实内容仍须来源核验与专业审核

## `Source`

| 字段 | 约束 | 含义 |
|---|---|---|
| `id`, `version` | 稳定 ID、不可变版本 | 来源快照标识 |
| `title`, `publisher` | 必填 | 文件标题与发布机构 |
| `url_or_archive_ref` | 必填 | 官方链接或受控归档位置 |
| `published_at`, `checked_at` | 必填 | 发布与最近核验时间 |
| `jurisdiction`, `effective_status` | 必填 | 地区及 `current/superseded/withdrawn` |
| `content_hash` | 必填 | 归档完整性摘要 |

## `Ingredient`

| 字段组 | 必填内容 |
|---|---|
| 身份 | 标准名称、别名、物种、食用部位、普通食物/食药物质分类 |
| 准入 | 服务地区、目录状态、目录版本、Source ID |
| 使用 | 加工方式、份量单位、传统食用说明、替代候选 |
| 安全 | 过敏原、禁忌代码、特殊人群限制、停止条件 |
| 治理 | `draft/reviewed/published/retired`、版本、审核记录、发布时间 |

## `Recipe`

| 字段组 | 必填内容 |
|---|---|
| 身份 | 名称、版本、份数、目标标签 |
| 材料 | Ingredient 版本、食用部位、每份克数、允许替代 |
| 制作 | 前处理、顺序步骤、火候、时长、所需厨具 |
| 食用 | 建议频次、食用方式、预算/地域标签 |
| 安全 | 过敏原聚合、禁忌代码、停止条件、专业咨询条件 |
| 追溯 | Source ID、审核范围、状态、发布时间、停用原因 |

## `Contraindication`

| 字段 | 含义 |
|---|---|
| `code`, `version` | 稳定规则代码及不可变版本 |
| `subject_type`, `subject_id` | Ingredient、Recipe 或规则集合 |
| `trigger_type` | 过敏、用药、疾病、肝肾、孕哺、医生限制或资料缺失 |
| `trigger_value` | 受控代码；不得依赖自由文本自动诊断 |
| `action` | `block`、`professional_review` 或 `warn` |
| `message_template` | 经审核的非诊疗提示 |
| `source_ids`, `review_record_id` | 依据和签署记录 |
| `status`, `effective_from`, `retired_at` | 生命周期 |

## 通用约束

- 只有 `published` 且来源有效、审核范围覆盖当前用途的版本可进入候选集。
- AI 只能选择已发布 ID，不能创建新食材、剂量、功效、禁忌或来源。
- 方案保存 Ingredient/Recipe/Rule/Source 的版本快照，后续停用不改写历史记录。
- 来源撤回、规则停用或用户档案变化时，相关候选必须重新校验。
- 本文件定义字段和治理规则，不包含未经专业审核的医学阈值、疗效或用量。
