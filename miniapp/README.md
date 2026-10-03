# 云循微信小程序

技术栈：uni-app、Vue 3、TypeScript、Vite。M2 已通过自动化验收，默认仍运行在 `DEMO_MODE`。

推荐使用 Node.js 20 与 npm 10。当前官方模板未声明支持 Node.js 24。

## 当前范围

- 今日 / 食材 / 我的三栏原生 tabBar；
- 今日首页的日期、天气、主推荐和最多两条备选；
- 加载、错误和无天气降级结构；
- 五个首批城市的选择入口；
- 简化档案与本地缓存；
- 天气、日历和内容的可替换适配器；
- 正式构建的真实数据配置门禁。
- 仅在 `DEMO_MODE` 显示的 M1 验收场景入口：正常、加载中、无天气、错误、空数据。
- 香港天文台 2026 公历农历与 24 节气离线基线，以及开放 API 日历适配器；
- 腊八、春节、端午、中秋和立春、清明、白露、冬至 8 个 DEMO 内容包；
- 12 道字段完整的 DEMO 食谱、食谱详情页与过敏/不耐受过滤。

## 命令

```bash
npm install
npm run dev:mp-weixin
npm run type-check
npm run validate:m2
npm run build:mp-weixin
```

`npm run build:mp-weixin:release` 会在缺少真实主体、隐私联系人、天气提供方和内容签署版本时失败。当前不得用于正式发布。

## M1 交互验收

导入 `dist/build/mp-weixin` 后，在“今日”页顶部使用“M1 验收场景”依次检查五种状态。验收记录模板位于 `../docs/M1_ACCEPTANCE_RECORD.md`。该入口只在演示模式显示，不得作为正式功能发布。

## M2 日期与内容验收

“今日”页顶部的“M2 官方日期样例”可切换 4 个节日和 4 个节气。命中后应显示内容包说明，并优先展示对应食谱；点击主卡或备选卡可进入结构化详情页。自动化验收记录位于 `../docs/M2_ACCEPTANCE_RECORD.md`。
