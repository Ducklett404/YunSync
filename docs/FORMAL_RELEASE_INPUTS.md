# 正式数据与服务接入清单

更新时间：2026-10-08。本文描述工程已经支持的正式接入口，以及仍须由真实责任人提供的资料。配置完成不等于已经取得授权或签署。

## 1. 天气代理

小程序只请求不含密钥的 HTTPS 代理，服务凭据留在服务端。请求方式：

M12 云后端启用后，首选配置 `VITE_YUNSYNC_API_BASE_URL`，由后端的今日上下文和推荐 API 统一代理天气。`VITE_YUNSYNC_WEATHER_ENDPOINT` 保留为云 API 不可用时的无密钥兼容适配器。

```text
GET {VITE_YUNSYNC_WEATHER_ENDPOINT}?city=杭州
```

响应契约：

```json
{
  "city": "杭州",
  "temperature": 18,
  "feelsLike": 17,
  "humidity": 65,
  "precipitation": 0,
  "minTemperature": 12,
  "maxTemperature": 21,
  "text": "多云",
  "observedAt": "2026-10-05T08:00:00+08:00",
  "source": "正式供应商名称",
  "version": "provider-contract-v1"
}
```

客户端拒绝城市不一致、温湿度或降水范围异常、昼夜最低温高于最高温、过期及未来观测。正常数据缓存 30 分钟；请求失败可在 6 小时内使用已标识缓存，之后回退为无天气的季节通用内容。代理域名还须加入微信小程序合法请求域名。

## 2. 正式内容

将真实签署数据写入 `miniapp/src/data/official-content.json`。不要复制 DEMO 内容并改成 `approved`。发布门禁要求：

- 恰好 48 道有效食谱：粥 12、汤 12、菜 16、节庆食品 8；
- 至少 8 个已审核节日/节气内容包；
- 每道食谱包含用量、厨具、连续步骤、过敏原、禁忌、替代关系、正式来源、审核人和签署说明；
- `isDemo=false`、`reviewStatus=approved`；
- 食谱、内容包和内容库 `schemaVersion` 均等于 `YUNSYNC_CONTENT_SIGNOFF_VERSION`；
- 内容包只能引用当前可用、已审核的食谱。

## 3. 正式身份、隐私与问卷

在本地未提交的 `.env` 中配置：

```text
VITE_DATA_MODE=real
VITE_YUNSYNC_API_BASE_URL=https://华为云后端地址
VITE_YUNSYNC_API_TIMEOUT_MS=5000
YUNSYNC_MINIAPP_APPID=真实 AppID
VITE_YUNSYNC_LEGAL_ENTITY=法定运营主体
VITE_YUNSYNC_PRIVACY_CONTACT=真实隐私联系人或公开联系方式
VITE_YUNSYNC_PRIVACY_NOTICE_VERSION=已生效隐私说明版本
VITE_YUNSYNC_WEATHER_PROVIDER=已签约天气服务名称
VITE_YUNSYNC_WEATHER_ENDPOINT=https://不含密钥的天气代理地址
YUNSYNC_CONTENT_SIGNOFF_VERSION=正式内容签署版本
VITE_YUNSYNC_SURVEY_ENABLED=true
YUNSYNC_SURVEY_LICENSE_VERSION=体质问卷授权版本
```

用户现在可以在“我的”页导出当前设备内的云循数据，并撤回本机数据使用、删除档案、每日体感、推荐历史、天气缓存、收藏、浏览与反馈。若以后增加登录和云同步，服务端必须实现相同范围的导出、撤回和删除，并更新隐私说明。

问卷题库尚未收到授权。通用答题、结构化计分、结果保存和谨慎说明页面已经实现；审核结果可提供低权重 `recommendationTags`，只与食谱的已审核标签匹配。将经授权、经专业审核的题目、选项、评分和结果文案写入 `miniapp/src/data/official-survey.json` 后才显示入口。发布门禁会核对授权版本、审核信息、题目选项、结果标签和评分引用，空题库不能发布。

## 4. 仍需真实执行

- 微信开发者工具、Android、iOS、真实弱网和权限拒绝测试；
- 3—5 人走查和 10—20 人封闭试用；
- 专业内容、安全、隐私、真实用户和发布负责人签署；
- 正式讲解视频、线上回滚演练、提审与发布。

这些项目应填写真实证据到 `M6_TRIAL_RESULTS.json`。工程检查会拒绝空记录、低于 90% 的核心任务完成率、未关闭 P0/P1 或缺少任一签署。
