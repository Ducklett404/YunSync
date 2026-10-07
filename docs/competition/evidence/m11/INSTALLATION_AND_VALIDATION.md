# M11 本机安装与验证证据

记录日期：2026-10-07

本文件记录可重复验证的工具安装和工程结果，不替代 CodeArts AI 会话证据。

## CodeArts Agent IDE

- 安装版本：由 `26.9.500` 安装，并通过 IDE 内置更新升级到 `26.9.501`。
- 安装包：`codearts-agent-x64-26.9.500-1f505f1.exe`。
- 安装包 SHA256：`30E04CDB1FC95133B7BB627848552563D9ADE08135EFC7325B22F0A491209622`。
- 数字签名：有效；签名者 `Huawei Technologies Co., Ltd.`；证书指纹 `9C526D44C2BD5062F19EB6D13746187D7630E78F`。
- 登录方式：按照华为云官方 IDE 快速入门，通过 IDE 唤起浏览器并登录华为云账号，不依赖 AK/SK。
- 当前状态：IDE 已安装、账号已登录，项目所有者已明确同意首次启用条款；真实 AI 任务与截图证据已完成。

## CodeArts CLI

- 安装来源：华为云官方 OBS 安装脚本。
- 安装脚本 SHA256：`A526F6445C9DB0A4F6161170E4805029F34BE0708265245A14014C9019F6D571`。
- 安装版本：`26.9.13`。
- 安装路径：`%USERPROFILE%/.codeartsdoer/installers`。
- 默认权限配置：`bash_mode=sandbox`。
- 默认网络配置：`network_policy=deny_all`。
- 当前授权状态：未设置 `CODEARTS_CLI_AK` 和 `CODEARTS_CLI_SK`；IDE 账号登录是当前 M11 的执行路径，因此该状态不阻塞 IDE 验收。

## auto-deploy Skill

- 来源：`https://gitcode.com/weixin_43883336/auto-deploy.git`。
- 安装位置：`%USERPROFILE%/.codeartsdoer/skills/auto-deploy`。
- Git 提交：`971a801cf0917f2e86365d09b0ed58a93ca27262`。
- Windows 兼容处理：仅把安装目录下 `.sh` 文件从 CRLF 规范化为 LF。
- 离线 self-check：通过。
- 自检凭据：只在自检进程内使用不可用的占位字符串，没有保存或调用真实账号凭据。
- 自检范围：Python 编译、shell 语法、项目分析、plan-only、环境变量缺失阻断、脱敏、预检和 Dockerfile 优化。

## Terraform

- 来源：HashiCorp 官方发布站。
- 版本：`1.16.5`，满足 auto-deploy 模板的 `>= 1.9.0` 要求。
- 平台：Windows AMD64。
- SHA256：`01700102B7291F95C0AB61394B55BFD5F57A12AC65632C2C1958691C8CF438EF`。
- 安装路径：`%USERPROFILE%/.codeartsdoer/tools/terraform/1.16.5`。
- 已加入当前用户 PATH；新终端启动后生效。

## YunSync 项目验证

- M11 Agent/Skills 结构检查：17/17 通过。
- TypeScript 类型检查：通过。
- M2、M3、M4、M5、M6 工程验证：通过。
- H5 构建：通过。
- 微信小程序构建：通过。
- 报告：`docs/competition/generated/M11_VALIDATION_REPORT.md`。

## CodeArts 真实任务

- 需求理解：调用 `yunsync-cloud-plan` 与 `yunsync-cloud-agent`，核对并补齐云资源计划。
- 代码生成/问题修复：同步修复资源计划与部署计划生成器，双次生成结果稳定。
- 项目构建：CodeArts 调用 `yunsync-validate --full`，8/8 通过。
- 部署能力：CodeArts 调用 `yunsync-deploy` 完成 `plan-only` 预检；未执行云资源变更。
- 会话截图：`docs/competition/evidence/m11/codearts-m11-session.png`。
- 证据登记：`docs/competition/CODEARTS_EVIDENCE.md`。

## 构建问题与修复

DCloud 构建链默认使用 Terser；在当前 Node 24 与固定 Vite 5.2.8 组合下，即使显式安装 Terser，Vite 仍错误报告无法解析。项目已在 `miniapp/vite.config.ts` 中选择 DCloud CLI 支持且构建链已包含的 `esbuild` 压缩器，随后 H5 和微信构建均通过。

该修复由当前开发过程完成，不能登记为 CodeArts 智能体修复证据。码道 IDE 完成账号登录并真实执行任务后，另行填写 `docs/competition/CODEARTS_EVIDENCE.md`。
