# M14 云端发布手册

当前状态：**代码与本地预检就绪；尚未创建 CodeArts 流水线或华为云资源，尚无公网 Demo**。云端运行结果见 `docs/competition/M14_ACCEPTANCE_RECORD.md`。

## 前置条件

1. 项目所有者确认 Region、ECS/RDS/DCS/OBS 规格、计费方式和预算上限。逐项核对 `docs/competition/generated/CLOUD_RESOURCE_PLAN.md`。
2. 完成 RDS/DCS 内网联通、MaaS V2 开通和域名/HTTPS 证书。天气服务也需要正式地址和服务端凭据。所有 DEMO 内容保持 `isDemo` 标识。
3. 使用 `yunsync-validate --full` 验证仓库；若以 Terraform 建资源，先保存 `terraform plan` 并复核资源清单、公网端口与费用。SSH 仅开放控制机 `/32`；RDS/DCS 不开放公网。
4. 在 CodeArts Repo 中镜像与 GitHub 同一提交。官方文档当前要求 YAML 流水线以 **CodeArts Repo** 为代码源；GitHub 继续作为开源仓库。比对两端完整 SHA，禁止按浮动 `main` 制品发布。

## CodeArts Build

使用 Ubuntu/Linux 构建环境，提供 Node.js、Python 3.12、Docker；在 CodeArts Build 中设置非敏感变量 `VITE_YUNSYNC_API_BASE_URL=https://<API 域名>`。构建命令：

```bash
bash deploy/m14/build-release.sh
```

命令依次完成 `npm ci`、TypeScript、M2—M6、H5 构建、后端 pytest、Docker 镜像构建。产物 `deploy/m14/out/` 含 H5 tar、API 镜像 tar、SHA256 清单和发布脚本。把整个目录发布到 CodeArts 软件发布库，以完整 Git SHA 命名；构建任务失败时不得触发部署。

## CodeArts Deploy

在同一个 CodeArts 项目中创建两个环境：`test` 与 `demo`。每个环境分别配置：ECS 主机集群、OBS 桶、H5 HTTPS 地址、API HTTPS 地址、RDS/DCS/MaaS/天气变量。密钥只使用平台安全参数或 ECS 上 mode `600` 的 `/etc/yunsync/api.env`；构建变量与日志不包含密钥。`api.env` 至少包括 `YUNSYNC_APP_ENV=production`、RDS/DCS URL、MaaS URL/model/key、天气 URL/key、`YUNSYNC_ALLOW_DEMO_CONTENT=true`、`YUNSYNC_SEED_DEMO_CONTENT=true`、与 H5 域名一致的 `YUNSYNC_CORS_ORIGINS`。此配置仅适用于比赛 DEMO。

CodeArts Deploy 应用步骤：

1. 从软件发布库下载**本次 SHA 的**产物至 `/opt/yunsync/releases/<SHA>/`，不得取 latest。
2. ECS 预装 Docker、Nginx、Python 3.12、obsutil。OBS 访问采用最小权限委托或安全变量。配置 HTTPS API 站点，参考 `nginx-api.conf.example`；创建 `/etc/nginx/snippets/yunsync-upstream.conf`。DNS、证书和 OBS 静态网站托管/自定义域名在控制台配置。
3. 使用 sudo 的普通执行 Shell 脚本 `deploy-release.sh <SHA> <release_dir> <bucket> <API_URL> <H5_URL>`。它先上传 OBS 静态资源、最后切换 `index.html`，再启动候选 API。候选容器通过 RDS/DCS 内网健康检查后才切换 Nginx；公网验证还要求 MaaS 真调用为 `assisted`。任一步骤失败会恢复先前 API 与 H5 入口。
   首次空桶发布时才设置 `YUNSYNC_FIRST_DEPLOY=true`；后续发布必须能备份旧入口，否则停止。
4. CodeArts Deploy 的“失败后继续运行”保持关闭；保存任务运行号、目标 SHA、健康检查 JSON 与运行时间。若自动回滚 OBS 失败，立即在部署任务中处理并记录原因。

`codearts-pipeline.yaml.example` 是关联已有 Build/Deploy 任务的模板。把两个真实任务 ID 填入后存入 CodeArts Repo，再在 CodeArts Pipeline 中选择 YAML 化编排并关联该文件。流水线运行时核对触发提交 SHA 与 `release.json.gitCommit`；Build 成功后才允许 Deploy。CodeArts Deploy 任务本身负责环境变量与发布步骤，模板中的占位符不是已建成的流水线。云端编辑器验证后保留截图和运行号。

## 回滚与销毁

- API：旧槽位保持运行。`rollback-api.sh <API_URL> <H5_URL>` 检查旧槽位并切回；如涉及不兼容数据库迁移，先按 RDS 快照与迁移方案处理，不能只切容器。
- H5：`rollback-h5.sh <失败的 SHA> <OBS 桶>` 恢复发布前备份的 `index.html`。OBS 应启用多版本控制并保留旧资源；如有 CDN，刷新入口缓存后再验收。
- 资源销毁：从部署记录找到**本次** Terraform workdir 与 state，先 `terraform plan -destroy` 并逐项核对 ECS/RDS/DCS/OBS/VPC/IAM 清单及数据备份；另行得到项目所有者对销毁清单的确认后，才在该 workdir 执行 `terraform apply`。关联的既有资源不能随此演示环境删除。此仓库没有可安全执行的通用一键销毁命令。

## 验收命令

```bash
python3 deploy/m14/smoke.py --api-base https://<API 域名> --h5-url https://<H5 域名> --expected-sha <完整 Git SHA>
```

输出只有检查名、依赖状态和模型参与状态；不会记录健康原文、密钥或完整请求。该命令要求健康检查为 `ok`，数据库为 PostgreSQL、缓存为 Redis，并看到 MaaS `assisted`。测试覆盖腊八节、体感、食材、自然语言与 H5 入口。单独的浏览器页面回归仍需人工或 Playwright 验证。

官方依据：[CodeArts YAML 流水线](https://support.huaweicloud.com/usermanual-pipeline/pipeline_01_0024.html)、[CodeArts Deploy 插件](https://support.huaweicloud.com/usermanual-pipeline/pipeline_01_0086.html)、[Deploy Shell 步骤](https://support.huaweicloud.com/usermanual-deployman/deployman_hlp_1050.html)、[OBS 静态网站 HTTPS](https://support.huaweicloud.com/helppanel-obs/obs_98_0012.html)、[OBS 多版本控制](https://support.huaweicloud.com/usermanual-obs/zh-cn_topic_0045829098.html)。
