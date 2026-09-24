# 隐私数据运维手册

## 1. 配置

- `ACCOUNT_DELETION_GRACE_HOURS`：删除撤销期，默认 72，允许 24–720 小时。
- `EXPIRED_SESSION_RETENTION_DAYS`：过期或撤销会话的保留天数，默认 7，允许 1–90 天。
- 生产环境应由受控调度器调用命令，运行身份只取得应用数据库和私有对象删除所需权限。

## 2. 预览到期任务

以下命令只返回数量，不显示用户 ID、报告内容或对象键：

```powershell
\.venv\Scripts\python.exe scripts\privacy_ops.py process-deletions
\.venv\Scripts\python.exe scripts\privacy_ops.py purge-expired-sessions
```

## 3. 执行任务

```powershell
\.venv\Scripts\python.exe scripts\privacy_ops.py process-deletions --apply --confirm APPLY_DUE_ACCOUNT_DELETIONS
\.venv\Scripts\python.exe scripts\privacy_ops.py purge-expired-sessions --apply --confirm PURGE_EXPIRED_SESSIONS
```

建议每小时处理删除请求、每日清理过期会话。实际频率须按批准的保存政策设置。

## 4. 失败处理

对象存储删除失败时，请求保持 `pending`，`attempt_count` 增加，`last_error_code` 只保存通用代码。检查 OBS 权限、端点和网络后重跑同一命令；对象删除具有幂等性。不要绕过对象删除直接把请求标为完成。

连续失败应触发隐私运维告警。调查记录只引用删除请求 ID，不复制健康正文、文件名、对象键或凭据。

## 5. 完成证明

生产证据应包含执行时间、发布版本、迁移版本、任务汇总计数、失败数、告警编号和复核人。账号删除完成后只保留请求 ID、时间、状态和去关联的主体摘要，不保留健康正文。
