<!-- source: official websites listed below -->
<!-- fetched_at: 2026-09-29T17:10:00+08:00 -->
<!-- url: config/official-sources.json -->

# 官方网页补充核验记录（2026-09-29）

用途：补充本地 Node 网络栈无法读取的官方站点。该记录只证明本日直接查看到的公开规则，不代替后续自动检查、授权书、合同或签名。

| 来源 ID | 官方核验结果 | 核验地址 |
|---|---|---|
| `gbt-46939-2025` | 现行；2025-12-31 发布、2026-04-01 实施；主管和归口均为国家中医药局 | https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=827D6D266BA52A2983F93638DA871028 |
| `wechat-privacy` | 涉及个人信息的小程序需配置隐私保护指引；声明相应个人信息后方可调用对应隐私接口 | https://cloud.tencent.com/document/product/1301/97930 |
| `wechat-fuzzy-location` | `wx.getFuzzyLocation` 获取当前模糊地理位置；拒绝授权场景必须兼容 | https://intl.cloud.tencent.com/zh/document/product/1219/68054 |
| `pipl` | 医疗健康和行踪轨迹属于敏感个人信息；处理需特定目的、充分必要、严格保护并取得单独同意 | https://www.cac.gov.cn/2021-08/20/c_1631050028355286.htm |
| `internet-advertising-measures` | 禁止以健康、养生知识形式变相发布医疗等广告；同页不得出现相关购物链接、地址或联系方式 | https://www.samr.gov.cn/zw/zfxxgk/fdzdgknr/fgs/art/2023/art_d93a579afd45413e8576e4623fab348f.html |
| `advertising-law` | 保留为发布前法规核验来源；本地自动请求与本次浏览请求均超时，因此不得将其标为自动核验成功 | https://www.npc.gov.cn/npc/c1773/c1848/c21114/c25274/c25277/201905/t20190521_207459.html |

## 当前结论

- 5 个运行时/供应商来源已由同步脚本自动通过；
- 5 个被网络策略阻断的来源已直接在官方网页补充核验；
- 中国人大网广告法页面本次仍超时，保留失败状态；发布前必须再次核验；
- 不使用搜索摘要、博客或转载页面把失败状态伪装为成功。
