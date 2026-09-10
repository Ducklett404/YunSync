# M2A 工程基线验证记录

> 执行日期：2026-09-10
>
> 执行环境：Windows，本地合成数据
>
> 结论：M2A 本机验收通过；不等同于第 2 周全新 Linux/DevSpace 与容器冷启动验收

## 已通过

| 检查 | 执行方式 | 结果 |
|---|---|---|
| 后端、配置、文档和可观测性测试 | `scripts/verify.ps1` | 23 项通过；2 条第三方弃用警告 |
| 数据库升级 | `alembic upgrade head` | 通过 |
| 模型与迁移一致性 | `alembic check` | 无待生成升级操作 |
| 前端类型检查 | `npm run typecheck` | 通过 |
| 前端生产构建 | `npm run build` | 通过 |
| Compose 文件 YAML 结构 | Python + PyYAML 6.0.3 | 成功解析 `app`、`postgres`、`redis` 三个服务 |
| Git 差异卫生 | `git diff --check` | 通过 |
| Git 忽略规则 | `git check-ignore` | `.env*` 实例、数据库和依赖目录均被忽略；示例模板可入库 |

测试覆盖的新增工程风险包括：

- Staging/Production 拒绝默认密钥、SQLite 和通配 CORS；
- request ID 的透传、非法值替换和未知 API 路由 404；
- 未处理异常使用安全响应，不泄露内部错误消息；
- 500 响应仍包含 request ID 和允许来源的 CORS 响应头；
- 架构、数据字典、API 契约和三类环境模板保持存在并可追踪。

## 尚未执行

| 检查 | 原因 | 完成条件 |
|---|---|---|
| 全新 Linux/DevSpace 从零安装 | 本机没有可用 `sh`/Linux 验证环境 | 在全新环境安装依赖、迁移、启动并检查 `/healthz`、`/readyz` |
| Docker/Compose 干净构建与启动 | 本机没有安装 Docker 命令 | 在可用容器运行时执行构建、健康检查和服务连通性验证 |

以上两项在完成前继续保留为第 2 周完整验收的待办，不以模拟结果替代。
