# YunSync 部署计划

- 生成时间：2026-10-08T08:12:53.244Z
- 阶段：M11 部署能力预检
- 模式：**plan-only，不创建云资源**
- 基准：`docs/HUAWEI_CLOUD_M11_M14_PLAN.md` 第 135-163 行（M14）
- 资源计划对齐：`docs/competition/generated/CLOUD_RESOURCE_PLAN.md`
- 部署 Skill 约束：`.codeartsdoer/skills/yunsync-deploy/SKILL.md`

## 本机预检

| 项目 | 状态 | 用途 |
|---|---|---|
| CodeArts CLI | 就绪 | M11 必需 |
| auto-deploy Skill | 就绪 | M11 本机安装 |
| Git | 就绪 | 源码版本控制 |
| Node.js | 就绪 | 小程序构建 |
| Python | 就绪 | auto-deploy |
| Terraform | 就绪 | M14 创建 ECS 前必需 |
| 受版本控制的后端 | 就绪 | M12 必需 |

## 当前阻塞项

- 无

## 缺失前置条件分类

### 本机工具
- Terraform 不在系统 PATH（已安装在 `%USERPROFILE%/.codeartsdoer/tools/terraform/1.16.5/terraform.exe`，脚本判定就绪）
- CodeArts CLI 不在系统 PATH（已安装在 `%USERPROFILE%/.codeartsdoer/installers/bin/codearts.exe`，脚本判定就绪）

### 云端资源
- Region、计费方式和预算上限待用户明确确认
- VPC/ECS/RDS/DCS/OBS/IAM/安全组均未创建
- MaaS 服务与 API Key 未开通
- H5 自定义域名与 HTTPS 方案未确认

### 内容门禁
- M12 后端已纳入版本控制，`/health` 与核心 API 契约测试通过
- 后端 `/health` 与五个 M12 API 路由已实现并有契约测试
- `yunsync-validate` full 模式结果待确认
- 48 道正式审核食谱未交付（DEMO 内容不得进入生产）

## M14 执行门槛（来自 yunsync-deploy SKILL.md）

只有同时满足以下条件，才可以执行实际部署：

1. 用户明确确认 Region、ECS/RDS/DCS/OBS 资源、计费方式和预算上限。
2. M12 后端已纳入版本控制并提供 `/health`。
3. `yunsync-validate` full 模式通过。
4. 凭据仅存在于进程环境或 CodeArts 安全部署变量。
5. 已生成 Terraform plan，且人工复核没有意外资源和公网端口。

## 安全规则（来自 yunsync-deploy SKILL.md）

- 不把 `--yes` 视为用户对费用和公网开放的确认。
- 不使用 `--allow-missing-env` 绕过生产配置缺失。
- SSH 默认仅允许控制机公网 IP `/32`，不得默认开放 `0.0.0.0/0`。
- 销毁必须使用本次部署记录的 Terraform workdir，并在执行前再次确认资源列表。
- 任何日志和报告只显示变量名，不显示值。

## 资源清单（对齐 CLOUD_RESOURCE_PLAN.md）

| 资源 | 用途 | M14 角色 |
|---|---|---|
| VPC / 子网 / 安全组 | 隔离 API、RDS、DCS | 资源 Skill 创建 |
| ECS | 运行后端 API 与 `/health` | auto-deploy 或 CodeArts Deploy 创建 |
| RDS PostgreSQL | 食谱、内容版本、来源、审计 | 资源 Skill 创建，auto-deploy 不创建 |
| DCS Redis | 天气/推荐缓存、限流、幂等 | 资源 Skill 创建，auto-deploy 不创建 |
| OBS + 自定义域名 | H5、图片、演示材料 | 资源 Skill 创建，auto-deploy 不创建 |
| MaaS | 自然语言结构化与受控说明 | M13 开通，后端调用 |
| IAM / 委托 | 最小权限访问 | 资源 Skill 创建 |
| CodeArts Pipeline / Deploy | 构建、测试、部署、健康检查、回滚 | M14 建立 |

## auto-deploy Skill 边界

赛题提供的 `auto-deploy` Skill 只覆盖单台 ECS：创建 ECS、上传源码、启动应用和验证 `/health`。该 Skill **不创建 RDS、DCS Redis 或 OBS**。M14 必须先由 `yunsync-cloud-plan` 创建或关联这些资源，并把连接变量安全传入 `yunsync-deploy`，不得把 `auto-deploy` 描述为已经创建 RDS、DCS 或 OBS。

## CodeArts Pipeline 阶段（M14 要求）

1. 安装依赖
2. 类型检查
3. M2—M6 验证
4. H5 构建
5. 后端测试
6. 部署（ECS 后端 + OBS H5）
7. 健康检查（`/health` + 三条核心流程）

部署失败时停止发布并回滚到上一个健康版本。CodeArts Deploy 管理测试和演示环境参数。

## 可执行的 M14 步骤（带前置依赖标注）

| 步骤 | 操作 | 前置依赖 |
|---|---|---|
| 1 | 由 `yunsync-cloud-plan` 创建或关联 VPC、子网、安全组、IAM | 用户确认 Region、计费、预算 |
| 2 | 创建 RDS PostgreSQL 与 DCS Redis，从 ECS 子网验证内网连接 | 步骤 1 |
| 3 | 开通 MaaS，从后端完成受控调用 | M13 完成 |
| 4 | 生成 Terraform plan，人工复核无意外资源和公网端口 | 步骤 1-3 |
| 5 | 对 Terraform plan 和预计费用进行人工确认 | 步骤 4 |
| 6 | 使用 `auto-deploy` 或 CodeArts Deploy 发布 ECS 后端（含 `/health`） | M12 后端纳入版本控制、步骤 5 |
| 7 | 将 H5 发布至 OBS 与自定义 HTTPS 域名 | 步骤 5、域名与 HTTPS 方案确认 |
| 8 | 建立 CodeArts Pipeline 执行上述 7 个阶段 | 步骤 6-7 |
| 9 | 自动检查 `/health` 和三条核心流程（今日推荐、体感输入、食材匹配） | 步骤 8 |
| 10 | 失败时停止流量切换并回滚到上一健康版本 | 步骤 9 |
| 11 | 输出资源清单、部署摘要、测试报告 | 步骤 9 |
| 12 | 录制完整演示视频 | 步骤 9 |

若最终改用 FunctionGraph 部署后端，须保留同等的自动部署和回滚证据。

## 回滚与销毁步骤

### 回滚
- 部署失败时 CodeArts Pipeline 停止发布。
- 使用上一健康版本的镜像/制品重新部署。
- 健康检查失败时停止流量切换。

### 销毁
- 使用本次部署记录的 Terraform workdir。
- 执行前再次确认资源列表（VPC、ECS、RDS、DCS、OBS、IAM）。
- 按依赖反向顺序销毁：ECS → RDS/DCS → OBS → VPC/安全组/IAM。
- 不得销毁未由本次 Terraform 管理的资源。

## 明确不执行

本计划不调用 Terraform apply、华为云创建 API 或控制台购买操作，不创建、修改或销毁任何云资源，也不输出任何凭据值（AK/SK、API Key、数据库密码、Redis 密码、Cookie、SSH 私钥等）。`auto-deploy` Skill 只覆盖单台 ECS，不创建 RDS、DCS 或 OBS。未得到用户对具体资源、Region 和预计费用的明确确认前，只允许生成计划。

## 结论

M11 已具备生成部署计划和识别前置条件的能力。实际部署属于 M14，必须在 M14 执行门槛（5 条）全部满足、安全规则（5 条）全部遵守后执行。M12 后端代码门槛已满足；当前阻塞项为华为云 Region/预算确认、RDS/DCS 等资源创建与 M13 MaaS。

> 注：本文件由 `create-deployment-plan.mjs` 生成，M14 覆盖内容已同步到生成器模板，重新运行不会丢失。
