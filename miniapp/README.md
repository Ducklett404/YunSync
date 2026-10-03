# 云循微信小程序

技术栈：uni-app、Vue 3、TypeScript、Vite。M2—M5 工程验证通过，M6 试用与发布准备已建立，默认仍运行在 `DEMO_MODE`。

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
- 轻量安全档案、体感、高风险阻断和近期主推荐去重复；
- 食材、厨具、份数、时间和补购条件匹配；
- 收藏、最近浏览、四种本机反馈、内容停用与版本更新提示；
- H5 页面回归、实际内容发布检查与真实用户验收记录检查。

## 命令

```bash
npm install
npm run dev:mp-weixin
npm run type-check
npm run validate:m2
npm run validate:m3
npm run validate:m4
npm run validate:m5
npm run validate:m6
npm run build:mp-weixin
```

`npm run release:check` 和 `npm run build:mp-weixin:release` 会检查真实配置、AppID 一致性、实际内容状态、字段、审核人与冻结配额，并拒绝当前 DEMO 天气适配器。当前正式构建应失败。

## H5 自动化交互回归

使用已安装的 Microsoft Edge，创建独立测试会话。准备录像组件后运行：

```bash
npm exec playwright -- install ffmpeg
npm run validate:h5
```

测试服务器只监听 `127.0.0.1:5186`。结果、截图和录像存放于 `test-results/`（不提交）。该命令会构建 H5、启动测试服务器并在测试结束后停止自己启动的服务器。若使用其他已安装浏览器，可通过 `PLAYWRIGHT_CHANNEL` 指定；不使用用户浏览器登录状态。

## M6 试用与发布准备

`npm run validate:m6` 检查发布门禁和验收记录计算逻辑，合成测试数据只用于工程验证。

实际走查和封闭试用结果填写于 `../docs/M6_TRIAL_RESULTS.json`，运行 `npm run check:m6` 检查人数、90% 任务完成率、未关闭严重缺陷、设备证据和五类签署。未执行的空记录必须失败。

操作说明与流程见 `../docs/USER_MANUAL.md`、`../docs/M6_TRIAL_PLAN.md`、`../docs/M6_RELEASE_AND_ROLLBACK.md`。

## M1 交互验收

导入 `dist/build/mp-weixin` 后，在“今日”页顶部使用“M1 验收场景”依次检查五种状态。验收记录模板位于 `../docs/M1_ACCEPTANCE_RECORD.md`。该入口只在演示模式显示，不得作为正式功能发布。

## M2 日期与内容验收

“今日”页顶部的“M2 官方日期样例”可切换 4 个节日和 4 个节气。命中后应显示内容包说明，并优先展示对应食谱；点击主卡或备选卡可进入结构化详情页。自动化验收记录位于 `../docs/M2_ACCEPTANCE_RECORD.md`。
