---
name: yunsync-deploy
description: 为 YunSync 生成华为云部署预检、部署计划、健康检查与回滚步骤。用户要求部署、发布、上线、ECS、OBS、CodeArts Pipeline/Deploy、auto-deploy 或一键部署时使用；创建付费资源前必须再次确认具体资源和费用。
---

# YunSync Deploy

## M11 阶段

M11 只验证部署能力和生成部署计划。执行：

```powershell
node .codeartsdoer/skills/yunsync-deploy/scripts/create-deployment-plan.mjs
```

输出：`docs/competition/generated/DEPLOYMENT_PLAN.md`。

## M14 执行门槛

只有同时满足以下条件，才可以执行实际部署：

1. 用户明确确认 Region、ECS/RDS/DCS/OBS 资源、计费方式和预算上限。
2. M12 后端已纳入版本控制并提供 `/health`。
3. `yunsync-validate` full 模式通过。
4. 凭据仅存在于进程环境或 CodeArts 安全部署变量。
5. 已生成 Terraform plan，且人工复核没有意外资源和公网端口。

## auto-deploy 集成

用户级 Skill 安装位置：`%USERPROFILE%/.codeartsdoer/skills/auto-deploy`。

计划模式示例：

```powershell
python "$env:USERPROFILE/.codeartsdoer/skills/auto-deploy/scripts/auto_deploy.py" --repo . --app-name yunsync-api --region cn-north-4 --plan-only
```

`auto-deploy` 只创建单 ECS，不创建 RDS、DCS Redis 或 OBS。M14 必须先通过独立资源计划或基础设施代码准备这些服务，再以部署变量注入连接信息。

## 安全规则

- 不把 `--yes` 视为用户对费用和公网开放的确认。
- 不使用 `--allow-missing-env` 绕过生产配置缺失。
- SSH 默认仅允许控制机公网 IP `/32`，不得默认开放 `0.0.0.0/0`。
- 销毁必须使用本次部署记录的 Terraform workdir，并在执行前再次确认资源列表。
- 任何日志和报告只显示变量名，不显示值。
