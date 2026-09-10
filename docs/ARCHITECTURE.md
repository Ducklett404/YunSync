# 系统架构

## 分层原则

后端采用适合业务型 FastAPI 项目的分层 MVC：

- Controller：负责 HTTP 协议、参数校验和状态码。
- Service：负责健康安全规则、候选行动排序、实验随机化和结果计算。
- Repository：封装 SQLAlchemy 查询，不在控制器中拼接复杂查询。
- Model：定义持久化实体及约束。
- Schema：定义稳定的 API 输入输出契约。
- Integration：隔离华为云 OCR、MaaS、OBS 和 Redis，支持 Mock 与云端实现切换。

前端采用 View、Component、Store、Service 分层。页面不直接拼接请求地址，跨页面数据由 Pinia 管理。

## 核心数据关系

```text
UserProfile
  ├── HealthReport ── HealthMetric
  └── Experiment ── ActionTemplate
          └── Observation

AuditLog 独立保存报告解析、实验创建和每日记录事件。
```

## 关键设计决策

1. 行动模板来自审核后的库，大模型不能自由生成运动强度、膳食剂量或药物建议。
2. 同一用户同一时间只保留一个活动实验，新实验会暂停旧实验。
3. 随机种子和完整日程入库，保证实验安排可以复现和审计。
4. 结果只输出观察性差异、有效观测次数和限制，不输出疾病疗效。
5. SQLite 用于本地零配置运行，SQLAlchemy 和 Alembic 保证迁移到 PostgreSQL 时结构一致。

## 请求处理链路

```text
Browser / API Client
  -> CORS 与请求 ID 中间件
  -> FastAPI Controller + Pydantic 校验
  -> Service 业务规则与安全边界
  -> Repository / Integration
  -> SQLite/PostgreSQL、Redis、OCR、MaaS、OBS
```

每个响应携带 `X-Request-ID`。API 日志只记录方法、路径、状态码和耗时等最小元数据；未处理异常转换为通用 500 响应，不把堆栈或内部数据暴露给前端。详细规范见 [ENVIRONMENTS.md](ENVIRONMENTS.md)。

## 契约与数据

- 持久化实体、字段、外键、索引和业务约束见 [DATA_DICTIONARY.md](DATA_DICTIONARY.md)。
- HTTP 输入输出、状态码和错误口径见 [API_CONTRACT.md](API_CONTRACT.md)。
- 数据库结构只通过 Alembic 迁移演进；应用启动时执行幂等迁移和合成数据初始化。
- Local、DevSpace 和 Staging 使用独立配置模板，Staging/Production 对默认密钥、SQLite 和通配 CORS 执行启动失败保护。

## 已知演进项

1. 第 3 周增加账号、授权、撤回与角色实体，并把当前前端守卫升级为后端鉴权。
2. 第 5 周为行动模板增加审核状态、版本和停用机制。
3. 第 6 周补齐实验状态机和数据库级单活动实验约束。
4. 第 9 周在真实 RDS/DCS 环境执行迁移、备份和降级验证。
