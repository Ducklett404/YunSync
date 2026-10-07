---
name: yunsync-cloud-plan
description: 分析 YunSync 仓库并生成华为云资源与数据边界计划。用户询问华为云架构、VPC、ECS、RDS、DCS Redis、OBS、IAM、MaaS、预算、资源创建顺序或赛题云服务对齐时使用；该技能只生成计划，不创建资源。
---

# YunSync Cloud Plan

## 执行步骤

1. 读取 `docs/HUAWEI_CLOUD_M11_M14_PLAN.md` 和 `docs/PROJECT_STATUS.md`。
2. 运行：

   ```powershell
   node .codeartsdoer/skills/yunsync-cloud-plan/scripts/generate-cloud-plan.mjs
   ```

3. 检查生成的 `docs/competition/generated/CLOUD_RESOURCE_PLAN.md`。
4. 向用户说明资源用途、依赖、数据边界、当前阻塞项和费用风险。

## 约束

- 本技能不得调用 Terraform apply、华为云创建 API 或控制台购买操作。
- 不读取或显示任何凭据值。
- RDS 保存审核内容、版本和最小化审计数据；DCS Redis 只保存有 TTL 的缓存和限流数据。
- 原始健康描述默认不持久化，不把用户敏感数据写入生成计划。
- `auto-deploy` 只覆盖单 ECS，不得把它描述为已经创建 RDS、DCS 或 OBS。

## 输出

- `docs/competition/generated/CLOUD_RESOURCE_PLAN.md`
- 资源清单、创建顺序、最小权限边界、部署前置条件和未满足项。
