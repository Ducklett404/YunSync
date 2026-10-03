# YunSync V3 · M2 实现记录

日期：2026-09-29  
范围：`V3_MINI_PROGRAM_REDESIGN_PLAN.md` 的 M2（日历、节气、节日与内容库）  
数据状态：`DEMO_MODE`；日期基线来自官方公开数据，食谱仍为待专业签署的演示内容

## 已实现

- 以香港天文台 2026 公历农历对照表建立年度离线日期基线，并保留公开 API 适配器。
- 以香港天文台 2026 二十四节气 XML 建立 24 节气日期和香港时间（UTC+8）基线。
- 建立腊八、春节、端午、中秋 4 个传统节日内容包。
- 建立立春、清明、白露、冬至 4 个节气内容包。
- 内容包包含日期规则、名称、文化说明、地域标签、食谱引用、来源、版本和审核状态。
- 建立 12 道结构化演示食谱，覆盖粥、汤、菜、饭和节庆食品；每道包含人数、克数/用量、前处理、厨具、4—8 个单动作步骤、替代、过敏原、不适用情况、场景标签、来源说明与版本。
- 首页在 DEMO 模式下可切换 8 个 M2 官方日期样例，命中内容包后优先显示节庆/节气食谱。
- 新增食谱详情页；首页主推荐和备选均可进入。
- 内容包进入推荐前执行限制项过滤；“蒜不耐受”会完全排除腊八蒜。
- 正式数据适配器通过香港天文台开放 API 获取农历；接口失败时使用已校验离线基线降级。

## 官方来源边界

- 公历/农历年度表：`https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T2026c.txt`
- 二十四节气 XML：`https://www.hko.gov.hk/tc/gts/astronomy/data/files/24SolarTerms_2026.xml`
- 农历开放 API：`https://data.weather.gov.hk/weatherAPI/opendata/lunardate.php`

官方日期来源只证明日期和节气信息。文化说明、配方、克数、食品安全条件和替代关系仍是演示内容，不得解释为香港天文台背书，也不得在未完成正式来源授权和专业签署前进入生产推荐。

## 验证命令

```text
npm run type-check
npm run validate:m2
NODE_OPTIONS=--max-old-space-size=4096 npm run build:mp-weixin
node scripts/assert-production-data.mjs
```

前三项应通过；最后一项在当前阶段必须失败并列出真实主体、隐私联系人、天气服务与内容签署等缺失配置。
