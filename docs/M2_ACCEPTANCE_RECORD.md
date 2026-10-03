# YunSync V3 · M2 验收记录

验收依据：`V3_MINI_PROGRAM_REDESIGN_PLAN.md` M2  
执行日期：2026-09-29  
状态：**自动化验收通过；DEMO 内容不得发布**

| 验收项 | 结果 | 证据 |
|---|---|---|
| 日期命中正确 | 通过 | 8 个示例日期与香港天文台 2026 官方年度表/节气 XML 一致 |
| 4 个节日示例 | 通过 | 腊八、春节、端午、中秋内容包共 4 个 |
| 4 个节气示例 | 通过 | 立春、清明、白露、冬至内容包共 4 个 |
| 节庆内容安全过滤 | 通过 | `蒜不耐受` 后仅保留腊八粥，腊八蒜完全排除 |
| 食谱字段完整率 | 100% | 12 道食谱 × 20 个必填字段，共 240 项字段检查无错误 |
| 食谱步骤约束 | 通过 | 每道均为 4—8 个有序单动作步骤 |
| 类型检查 | 通过 | `npm run type-check` 退出码 0 |
| 微信小程序构建 | 通过 | `npm run build:mp-weixin` 退出码 0 |
| 正式发布门禁 | 通过（按预期阻断） | `assert-production-data.mjs` 拒绝当前 DEMO 构建 |

`npm run validate:m2` 输出摘要：

```json
{
  "bundles": 8,
  "recipes": 12,
  "solarTerms": 24,
  "recipeFieldChecks": 240,
  "fieldCompleteness": "100%",
  "garlicIntoleranceRemaining": ["m2-laba-porridge"],
  "errors": []
}
```

## 进入 M3 的边界

M2 的工程验收不等于内容专业签署。M3 可以在 `DEMO_MODE` 下继续实现个人情况、安全硬过滤和推荐排序；真实食谱来源、授权、审核人和签名仍保持为 M5/M6 发布硬门槛。
