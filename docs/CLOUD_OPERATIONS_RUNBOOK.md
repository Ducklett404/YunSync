# YunSync 云数据库、缓存与凭据运行手册

> 版本：V0.1
>
> 日期：2026-09-12
>
> 当前状态：工具与本地契约已验证；真实 RDS、DCS、IAM 和备份恢复尚未执行

## 1. 执行边界

本手册用于 M9B 真实云联调。仓库中的离线迁移 SQL、Redis 故障替身、配置预检和 dry-run 只能证明工程准备度，不能作为华为云资源已创建、真实调用成功或真实备份可恢复的证据。

所有联调只使用合成账号和合成健康记录。不得把真实数据库密码、Redis 密码、AK/SK、MaaS 密钥、连接串或控制台会话写入仓库、命令截图和应用日志。

## 2. 配置与 IAM 前置检查

1. 在同一区域和受控网络内准备 RDS PostgreSQL、DCS Redis 与应用运行环境，数据库和缓存不开放公网入口。
2. 为应用建立独立身份，只授予运行所需资源范围；部署与运维身份分离，备份恢复权限不授予普通应用进程。
3. 优先设置 `HUAWEI_CREDENTIAL_MODE=instance_metadata` 使用运行实例身份；无法使用时由部署平台密钥服务注入 AK/SK，不写入镜像或 `.env.*.example`。
4. 将 `.env.staging.example` 复制到部署环境的受保护配置区并替换全部 `CHANGE_ME`。
5. 为一次性迁移任务注入 `MIGRATION_DATABASE_URL`，为应用注入只具备运行期读写权限的 `DATABASE_URL`；Production 设置 `RUN_MIGRATIONS_ON_STARTUP=false`。
6. 执行只读预检：

```bash
python scripts/cloud_preflight.py --env-file .env
```

`cloud-preflight-v4` 分开报告适配器代码状态与真实云验收状态。OBS 私有读写、OCR 保守解析和 MaaS 结构化调用均已有契约测试；只有在真实环境完成三项脱敏验收，并分别填写 `HUAWEI_OBS_VALIDATION_REF`、`HUAWEI_OCR_VALIDATION_REF`、`HUAWEI_MAAS_VALIDATION_REF` 后，`provider_live_acceptance` 才会通过。预检不访问云端，记录编号也不能替代原始日志和截图。

OBS 使用 `HUAWEI_OBS_ENDPOINT` 与私有桶；MaaS 使用完整的 V2 Chat Completions 端点、API Key 和 `HUAWEI_MAAS_MODEL`。环境凭据模式由部署平台注入 AK/SK，实例元数据模式使用 ECS 安全提供器。官方实现依据见[华为云 OBS Python SDK 安装](https://support.huaweicloud.com/intl/en-us/sdk-python-devg-obs/obs_22_0400.html)、[OBS 流式上传](https://support.huaweicloud.com/intl/en-us/sdk-python-devg-obs/obs_22_0902.html)、[OBS 内存读取](https://support.huaweicloud.com/intl/en-us/sdk-python-devg-obs/obs_22_0911.html)和[MaaS V2 模型调用](https://support.huaweicloud.com/model-call-maas/model-call-019.html)。

## 3. 空 RDS 迁移

先使用只具备目标数据库结构变更权限的迁移身份设置 `DATABASE_URL`（Compose 中对应 `MIGRATION_DATABASE_URL`），再执行：

```bash
python -m alembic upgrade head
python -m alembic current
python -m alembic check
```

若发布流程要求预审 SQL，可在不连接数据库时生成 PostgreSQL 脚本：

```bash
python -m alembic upgrade head --sql
```

离线脚本只用于空数据库。已有历史数据时必须在线执行，使 M6 迁移完成日程摘要和时间字段回填。验收证据应包含脱敏后的 RDS 实例标识、迁移版本、执行时间和 `/readyz` 数据库状态，不包含连接串。

## 4. DCS Redis 联调与降级

1. 设置 `CACHE_ENABLED=true`、独立 `CACHE_NAMESPACE` 和 DCS `REDIS_URL`；可用 TLS 时使用 `rediss://`。
2. 确认 `/readyz` 返回 `dependencies.cache=redis`、`degraded=false`。
3. 读取候选行动两次，确认缓存只保存版本化行动解释，不保存用户报告、档案、实验记录或会话令牌。
4. 在受控窗口阻断缓存连接，确认 `/readyz` 仍返回 200、缓存状态变为 `memory_fallback`，候选行动和核心数据库流程仍可运行。
5. 恢复连接并确认状态重新变为 `redis`。

连接超时受 `CACHE_CONNECT_TIMEOUT_SECONDS` 和 `CACHE_SOCKET_TIMEOUT_SECONDS` 限制。缓存内容带 TTL，读取命中后仍执行 `action-explain-v1` 输出安全校验。

## 5. 备份与恢复演练

工具只从 `DATABASE_URL` 环境变量读取目标，密码通过 `PGPASSWORD` 传给 PostgreSQL 客户端，不放入命令参数。先执行 dry-run：

```bash
python scripts/postgres_ops.py backup --target backup/yunsync.dump --dry-run
python scripts/postgres_ops.py restore --source backup/yunsync.dump --confirm-database yunsync --dry-run
```

实际备份需要本机安装 `pg_dump`，成功后生成 `.dump` 和 `.dump.sha256`：

```bash
python scripts/postgres_ops.py backup --target backup/yunsync.dump
```

恢复只能在隔离的空白验收数据库执行。`--confirm-database` 必须与连接串数据库名完全一致；恢复会使用 `--clean --if-exists`，不得指向生产数据库：

```bash
python scripts/postgres_ops.py restore --source backup/yunsync.dump --confirm-database yunsync_restore_check
python -m alembic current
```

恢复后使用合成账号核对表数量、最新迁移版本和核心流程，再销毁隔离验收资源。数据库服务自身的自动备份与时间点恢复策略还需在 RDS 控制台单独配置并验证。

## 6. M9B 证据清单

- [ ] RDS 和 DCS 私网拓扑、区域与脱敏资源标识；
- [ ] IAM 应用身份、运维身份及最小权限复核记录；
- [ ] 空 RDS 从 base 到 head 的迁移日志与 `/readyz`；
- [ ] DCS 正常命中及断连后 `memory_fallback` 的请求记录；
- [ ] 备份文件摘要、隔离库恢复日志和恢复后业务核对；
- [ ] 日志与截图已检查，不包含连接串、密码、AK/SK、API 密钥或真实健康数据。

上述项目全部完成前，第 9 周真实云联调不得标记完成。
