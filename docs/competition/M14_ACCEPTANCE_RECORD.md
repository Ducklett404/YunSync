# M14 一键部署、流水线与云上 Demo 验收记录

更新日期：2026-10-10。状态：**发布工程与本地验证已完成；云端部署与公网验收未完成**。

## 已交付的工程内容

- `deploy/m14/build-release.sh`：按 Git SHA 安装依赖、执行类型检查、M2—M6、H5 构建、后端测试，打包 API 镜像及 H5，写出 SHA256 清单。
- `deploy/m14/codearts-pipeline.yaml.example`：CodeArts Build → Deploy 流水线模板。仍需在实际 CodeArts 项目创建任务并填写 ID；该模板本身不证明流水线已运行。
- `deploy/m14/ecs-release.sh`：双槽位候选容器、RDS/DCS 健康预检、Nginx 切换、公网冒烟检查与失败自动恢复。
- `deploy/m14/publish-h5.sh`：校验产物、先上传静态资源、备份旧入口、最后更新 OBS `index.html`，失败恢复旧入口。
- `deploy/m14/deploy-release.sh`：CodeArts Deploy 单入口，依次发布 H5 与 API；API 失败时同时回滚 H5。
- `deploy/m14/rollback-api.sh`、`rollback-h5.sh`：手工回滚入口。
- `deploy/m14/smoke.py`：验证完整 Git SHA、`/health`、RDS、DCS、腊八节、体感、食材、自然语言 MaaS 与 HTTPS H5。只打印状态摘要。
- 根 README、架构、部署与销毁步骤、DEMO 边界；本地预览截图路径。

## 本地验证记录

| 检查 | 结果 | 证据 |
|---|---|---|
| Python 语法与后端测试 | 31/31 通过 | `python -m py_compile`；在 `backend/` 运行 pytest |
| `yunsync-validate --full` | 8/8 通过 | `docs/competition/generated/M11_VALIDATION_REPORT.md` |
| H5 页面回归与截图 | 9/9 通过 | `docs/competition/demo/m14-local-preview.png`；`m14-local-flow.webm` |
| M14 冒烟脚本本地降级模式 | 5 项通过 | `/health`、腊八节、今日体感、食材、自然语言；数据库/缓存/MaaS 均如实标记降级 |
| Bash 发布脚本语法 | 通过 | `bash -n deploy/m14/*.sh` |
| Linux 制品打包、OBS/ECS 真部署和故障回滚 | 未执行 | CodeArts 任务、Terraform plan 与云资源尚未具备；当前仅完成代码和语法检查 |

## 云资源清单与费用

| 资源 | Region / 标识 | 状态 | 计费 / 预算 |
|---|---|---|---|
| VPC、子网、安全组、IAM 委托 | 待确认 | 未创建或未关联 | 待确认 |
| ECS + HTTPS API 域名 | 待确认 | 未创建或未关联 | 待确认 |
| RDS PostgreSQL | 待确认 | 未创建或未关联 | 待确认 |
| DCS Redis | 待确认 | 未创建或未关联 | 待确认 |
| OBS + HTTPS H5 域名 | 待确认 | 未创建或未关联 | 待确认 |
| MaaS V2 模型 | 待确认 | 尚未开通 | 待确认 |
| CodeArts Build/Pipeline/Deploy | 待确认 | 未创建本项目 M14 任务 | 待确认 |

## 云端验收待办

1. 项目所有者确认 Region、每项资源规格、计费方式和预算上限，并提供可用域名/证书方案。任何密钥不放入聊天或 Git。
2. 资源 Skill 或经审阅的基础设施代码创建/关联 VPC、ECS、RDS、DCS、OBS、IAM 与安全组，先生成 Terraform plan 并人工复核费用和端口。
3. 从 ECS 完成 RDS/DCS 内网联调和 MaaS V2 真实调用；记录脱敏请求 ID、依赖状态和调用证据。
4. 在 CodeArts Repo 镜像固定 SHA，创建 Build/Deploy 任务与 YAML Pipeline；实际运行后记录任务 ID、运行号、日志路径和截图。
5. 使用公网 HTTPS 链接完成今日、体感、食材三流程、自然语言和 `/health`，检查 Git SHA 一致性；录制完整视频并填入链接。
6. 执行一次故障回滚演练与资源销毁预览，保存记录；正式销毁须另行复核清单。

**只有以上云端证据完成，才可把 M14 标记为已验收。**
