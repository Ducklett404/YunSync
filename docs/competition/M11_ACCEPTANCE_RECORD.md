# M11 CodeArts 赛题合规验收记录

更新时间：2026-10-07

## 当前结论

状态：**M11 工程配置、真实 CodeArts AI 任务和本地验收已完成**

CA-01—CA-05 已登记真实 CodeArts 会话、文件改动、验证报告和截图。CA-05 是 M11 的 `plan-only` 部署能力预检；M14 云端上线仍须单独完成。

## 本机安装

| 项目 | 结果 | 证据 |
|---|---|---|
| CodeArts Agent IDE | 已安装并更新 | 由签名安装包 `26.9.500` 安装，已通过 IDE 内置更新升级到 `26.9.501` |
| CodeArts CLI | 已安装 | 官方脚本安装，版本 `26.9.13` |
| 默认安全配置 | 已建立 | `bash_mode=sandbox`、`network_policy=deny_all` |
| auto-deploy Skill | 已安装到用户级 Skills | Git 提交 `971a801cf0917f2e86365d09b0ed58a93ca27262`；离线 self-check 通过 |
| Terraform | 已安装 | HashiCorp 官方 `1.16.5`，SHA256 已与官方校验和匹配 |
| IDE 登录 | 已完成 | 使用华为云账号登录，无需创建 AK/SK |
| CodeArts CLI 授权 | 非当前阻塞项 | 本机未设置 `CODEARTS_CLI_AK/SK`；仅在后续确需无人值守 CLI 时再配置 |

## 项目级交付物

- [x] `.codeartsdoer/agents/yunsync-cloud-agent.md`
- [x] `.codeartsdoer/skills/yunsync-cloud-plan/`
- [x] `.codeartsdoer/skills/yunsync-validate/`
- [x] `.codeartsdoer/skills/yunsync-deploy/`
- [x] `.codeartsdoer/skills/ProjectSkillStatus.txt`
- [x] `.codeartsdoer/.codebaseignore`
- [x] M11 本地结构校验脚本
- [x] 云资源计划和部署预检报告
- [x] CodeArts 实际完成一项需求实现：补齐云资源计划和 M14 部署计划
- [x] CodeArts 实际完成一次缺陷修复：修复两份生成器覆盖扩充内容的问题
- [x] CodeArts 实际执行一次获授权的 `plan-only` 部署演练
- [x] `CODEARTS_EVIDENCE.md` 的 CA-01—CA-05 全部补齐

## CodeArts 实际执行结果

- `yunsync-cloud-plan`：识别 10 项资源计划缺口，修订后 16 项核对全部对齐。
- `yunsync-cloud-agent`：作为子智能体执行资源计划和部署计划逐项核对。
- `yunsync-validate`：`quick` 和 `full` 均通过；最终 full 验证 8/8 通过。
- `yunsync-deploy`：完成 `plan-only` 部署预检，输出 M14 资源、Pipeline、健康检查、回滚和销毁步骤。
- 生成器缺陷：资源计划生成器连续生成两次均为 105 行；部署计划生成器连续生成两次均为 131 行。
- 安全结果：未运行 `terraform apply`，未创建、购买、修改或销毁任何华为云资源，未记录任何凭据值。

## 已发现并处理的问题

华为云官方安装脚本在本机旧版 Windows PowerShell 5 中出现语法解析错误；同一脚本经 PowerShell 7 解析检查无误并成功安装 CodeArts CLI。该记录只能作为安装问题处理证据，不能替代 CodeArts 智能体完成缺陷修复的证据。

用户级 `auto-deploy` Skill 首次检出时，Windows Git 自动把 `.sh` 文件转换为 CRLF，导致其自检拒绝执行；将该 Skill 内 shell 脚本规范化为 LF 后，自检通过。真实华为云凭据没有用于自检，测试仅在单个进程内使用不可用的占位字符串。

## 已执行的 IDE 任务

在码道 IDE 中单击“登录”，由浏览器完成华为云账号登录；随后打开本仓库，并在 `yunsync-cloud-agent` 中依次发送：

```text
调用 yunsync-cloud-plan 分析当前仓库并核对生成的华为云资源计划，不创建资源。
调用 yunsync-validate 运行 quick 验证，若失败则定位并修复首个由证据支持的问题。
调用 yunsync-deploy 生成 plan-only 部署预检，不创建或购买任何云资源。
```

上述任务均已执行并登记到 `docs/competition/CODEARTS_EVIDENCE.md`。真实截图位于 `docs/competition/evidence/m11/codearts-m11-session.png`。只有需要无人值守调用码道 CLI 时，才按照华为云官方文档单独配置 AK/SK。
