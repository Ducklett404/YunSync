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
  ├── AuthSession
  ├── ConsentRecord
  ├── HealthReport ── HealthMetric
  └── Experiment ── ActionTemplate
          └── Observation

AuditLog 独立保存报告解析、实验创建和每日记录事件。
```

## 关键设计决策

1. 行动模板来自审核后的库，大模型不能自由生成运动强度、膳食剂量或药物建议。
2. 同一用户同一时间只保留一个活动实验，新实验会暂停旧实验；服务层处理状态，数据库部分唯一索引处理并发兜底。
3. 随机种子、算法版本、锁定时间、完整日程和摘要入库；读取、记录和状态变化前重新校验日期、7:7 分组与摘要。
4. 结果只输出观察性差异、有效观测次数和限制，不输出疾病疗效。
5. SQLite 用于本地零配置运行，SQLAlchemy 和 Alembic 保证迁移到 PostgreSQL 时结构一致。
6. 报告字节与可查询元数据分离：本地开发把合成文件保存到非公开目录，数据库只存随机对象键、摘要、大小和处理状态；华为 OBS 适配器未配置时显式失败。
7. OCR 通过统一适配器返回原文、置信度和归一化位置；超时只有限重试，失败报告保留错误码但不写入任何指标。
8. 行动排序要求报告为 `confirmed` 且每个指标均已确认，防止数据库状态不一致时绕过逐项校对。
9. 行动模板以代码和版本联合唯一，实验保存具体模板 ID；启用新版本不会改写已有实验的历史引用。
10. Development 可发布“产品规则校验”模板，Production 只发布“专业审核通过”模板，两种状态不可混用。
11. 受控解释先经过 `action-explain-v1` 输出守卫；模型不可用或输出不安全时返回明确标记的固定解释。
12. 实验状态机仅允许 `active` 与 `paused` 间受控恢复，并从两者进入不可恢复的 `terminated` / `completed`；完成要求周期结束且 14 天记录齐全。
13. PostgreSQL 使用有界连接池和 `pool_pre_ping`；SQLite 保留本地测试专用连接参数，Staging/Production 只允许 psycopg 驱动。
14. Redis/DCS 只缓存不含用户健康数据的行动模板解释；缓存读取后再次通过输出守卫。连接失败时使用进程内 TTL 缓存，`/readyz` 标记降级但核心数据库流程继续运行。
15. Production 必须关闭演示登录和演示种子；云配置预检只输出状态，不回显连接串、AK/SK 或 API 密钥。
16. HTTP 边界采用 Host 白名单、精确 CORS、安全响应头、HTTPS 门禁和进程内滑动窗口限流；多实例共享限流仍由网关或 DCS 承担。
17. 生产容器以固定非 root 用户和只读根文件系统运行，删除 Linux capabilities；真实镜像构建、扫描和部署必须在具备 Docker 的环境留证。
18. 用户最近实验与报告指标排序使用组合索引；前端把 Vue 运行时和图表库拆成独立缓存块。

## 请求处理链路

```text
Browser / API Client
  -> CORS、Host、HTTPS、请求 ID、安全响应头与限流中间件
  -> Bearer 会话、角色权限、当前授权版本校验
  -> FastAPI Controller + Pydantic 校验
  -> Service 业务规则与安全边界
  -> Repository / Integration
  -> SQLite/PostgreSQL、Redis、OCR、MaaS、OBS
```

每个响应携带 `X-Request-ID`。API 日志只记录方法、路径、状态码和耗时等最小元数据；未处理异常转换为通用 500 响应，不把堆栈或内部数据暴露给前端。详细规范见 [ENVIRONMENTS.md](ENVIRONMENTS.md)。

## 契约与数据

- 持久化实体、字段、外键、索引和业务约束见 [DATA_DICTIONARY.md](DATA_DICTIONARY.md)。
- HTTP 输入输出、状态码和错误口径见 [API_CONTRACT.md](API_CONTRACT.md)。
- 数据库结构只通过 Alembic 迁移演进；应用启动时执行幂等迁移，合成数据初始化由 `SEED_DEMO_DATA` 控制并在 Production 强制关闭。
- Local、DevSpace 和 Staging 使用独立配置模板，Staging/Production 对默认密钥、SQLite 和通配 CORS 执行启动失败保护。

## 身份与授权边界

- 演示登录签发随机短期令牌，客户端只持有原始令牌，数据库只保存摘要；注销、过期或未知令牌返回 401。
- `participant` 可管理自己的授权与健康流程，`reviewer` 只能读取最小化审计事件；权限判断全部在后端执行。
- 健康接口从会话获取用户，不接受客户端指定 `user_id`，并对报告、实验执行对象归属校验。
- 只认可当前版本的活动授权。撤回后健康接口立即返回 403，同时暂停进行中的个人实验。
- 安全初筛任一项触发时，候选行动和新实验返回 409；答案正文不写入审计日志。

## 报告处理状态机

```text
上传校验 -> 私有存储 -> processing
                         ├─ OCR 成功 -> needs_confirmation
                         │              ├─ 逐字段确认/修正 -> confirmed
                         │              └─ 未全部确认 -> 排序保持阻断
                         └─ OCR 失败 -> ocr_failed -> 人工重试
                                           └─ 指标集合必须为空
```

本地私有存储用于不含真实数据的开发验证，不是 OBS 成功记录。真实 OBS 必须使用私有桶、服务端授权访问和独立生命周期策略，并在真实环境重新验证。

## 实验状态机

```text
创建并开始 -> active <-> paused
                |          |
                +-------> terminated
                |          不可恢复
                +-------> completed
                           需周期结束且 14 天记录齐全
```

每次转换写入不含记录正文的审计事件。撤回授权、触发高风险初筛或新建另一实验时，活动实验自动转为暂停并保存状态时间。

## 已知演进项

1. 正式身份提供方、验证码发送与账号恢复在部署方案明确后接入；Production 已禁止演示登录。
2. 行动模板治理机制已具备；首批模板仍需健康专业指导老师逐条复核，真实 MaaS 适配器仍待接入。
3. M9A 已完成 PostgreSQL 离线迁移兼容、Redis 降级和云配置门禁；仍需在真实 RDS/DCS 环境执行迁移、备份和故障验证。
4. IAM 最小权限范围和密钥注入路径必须在真实云资源创建后复核并留存证据。
5. M10A 已完成本地容器定义、安全门禁、依赖审计和合成并发烟测；公网 HTTPS、真实告警、镜像扫描和云端负载验证仍需在 M10B 完成。
