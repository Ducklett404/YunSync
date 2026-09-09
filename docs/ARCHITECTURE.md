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

