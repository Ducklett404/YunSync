# V2 M8 部署、交付与验收清单

## 1. 已完成的工程交付

- [x] 非 root 多阶段生产镜像、独立迁移任务和只读容器基线；
- [x] PostgreSQL 备份/恢复工具、HTTPS 代理示例和部署安全手册；
- [x] 受令牌保护的 `/internal/metrics`，只输出路由模板聚合指标；
- [x] `m8-release-preflight-v1`，分开报告工程状态和外部验收；
- [x] 两次报告的 V2 合成演示案例及自动校验；
- [x] 带清单和 SHA-256 的发布包工具；
- [x] 用户、管理员、隐私、内容运营、事故响应和审核记录文档。

## 2. 外部门禁

- [ ] 正式镜像摘要、SBOM、漏洞和秘密扫描记录；
- [ ] 空库迁移、真实 RDS 备份恢复和 HTTPS 验收；
- [ ] 指标采集、阈值告警和通知送达演练；
- [ ] RDS/DCS/OBS/OCR/MaaS 真实脱敏联调记录；
- [ ] 5–10 名目标用户测试和问题关闭记录；
- [ ] 专业、隐私、QA 与项目负责人审核签署；
- [ ] 正式演示视频及三轮 30 秒降级演练；
- [ ] 客户按 `V2_M8_CUSTOMER_ACCEPTANCE.md` 签收。

## 3. 自动检查

```powershell
python scripts/v2_demo_case_check.py
python scripts/release_preflight.py --env-file .env
python scripts/build_release_package.py --version V2.0
```

预检不输出秘密或验收编号。`engineering_ready=true` 只表示仓库交付齐全；只有 `external_acceptance_ready=true` 且 `ready=true` 才能宣称 M8 正式通过。
