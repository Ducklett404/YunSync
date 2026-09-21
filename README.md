# YunSync 云循 HealthLoop

云循正在按 V2 开发计划转向体检后的个体化食养随访。当前已可演示合成报告解析、逐项确认、结构化食养安全档案、风险分流，以及食材、食谱和禁忌知识库的审核发布流程；个体方案、周计划及复查迭代尚在建设。知识库种子均为候审草稿，不代表专业内容已经批准。旧版“候选行动—14 天个人实验”代码保留作为历史原型，已退出默认导航。

> 本项目仅用于健康教育、自我监测和生活方式支持，不提供疾病诊断、治疗或药物调整意见。仓库中的人物与健康数据均为合成数据。

## 项目文档

- [从 0 开始的详细开发计划书](docs/DEVELOPMENT_PLAN.md)
- [V2 首版指标字典技术草案](docs/V2_METRIC_CATALOG.md)
- [V2 初步安全分流规则](docs/V2_SAFETY_RULES.md)
- [V2 实施进度与自测记录](docs/V2_PROGRESS.md)
- [产品需求基线](docs/PRODUCT_REQUIREMENTS.md)
- [主流程与交互规格](docs/UX_FLOW.md)
- [界面文案基线](docs/CONTENT_COPY.md)
- [第 1 周可用性走查方案](docs/USABILITY_TEST_PLAN.md)
- [第 1 周合成用户仿真报告](docs/USABILITY_SIMULATION_REPORT.md)
- [系统架构](docs/ARCHITECTURE.md)
- [数据字典](docs/DATA_DICTIONARY.md)
- [API 契约草案](docs/API_CONTRACT.md)
- [环境与配置基线](docs/ENVIRONMENTS.md)
- [M2A 工程基线验证记录](docs/M2A_VERIFICATION_REPORT.md)
- [M3A 身份、授权与档案验证记录](docs/M3A_VERIFICATION_REPORT.md)
- [M4A 受控上传、OCR 契约与逐项校对验证记录](docs/M4A_VERIFICATION_REPORT.md)
- [合成 OCR 契约评测记录](docs/OCR_EVALUATION_REPORT.md)
- [V2 需求基线与追踪矩阵](docs/V2_REQUIREMENTS_TRACEABILITY.md)
- [V2 专业审核职责](docs/V2_REVIEW_RESPONSIBILITIES.md)
- [V2 内容数据字典 Schema](docs/V2_CONTENT_DICTIONARY_SCHEMA.md)
- [M1 验收单](docs/V2_M1_ACCEPTANCE.md)
- [M2 验收单](docs/V2_M2_ACCEPTANCE.md)
- [M3 验收单](docs/V2_M3_ACCEPTANCE.md)
- [M4 内容治理说明](docs/V2_CONTENT_GOVERNANCE.md)
- [M4 验收单](docs/V2_M4_ACCEPTANCE.md)
- [行动模板登记表](docs/ACTION_TEMPLATE_REGISTER.md)
- [M5A 行动模板治理、透明排序与解释安全守卫验证记录](docs/M5A_VERIFICATION_REPORT.md)
- [M6A 14 天实验状态机与锁定日程验证记录](docs/M6A_VERIFICATION_REPORT.md)
- [M7A 每日记录、应用内提醒与数据导入验证记录](docs/M7A_VERIFICATION_REPORT.md)
- [M8A 统计分析、受控复盘与下一轮决策验证记录](docs/M8A_VERIFICATION_REPORT.md)
- [M9A RDS/DCS/IAM 本地云就绪基线验证记录](docs/M9A_VERIFICATION_REPORT.md)
- [华为云迁移说明](docs/HUAWEI_CLOUD_MIGRATION.md)
- [云迁移、缓存、IAM 与备份恢复运行手册](docs/CLOUD_OPERATIONS_RUNBOOK.md)
- [M10A 部署、安全与性能本地基线验证记录](docs/M10A_VERIFICATION_REPORT.md)
- [部署、安全与性能运行手册](docs/DEPLOYMENT_SECURITY_RUNBOOK.md)
- [M11A 封闭测试与 RC1 本地基线验证记录](docs/M11A_VERIFICATION_REPORT.md)
- [RC1 缺陷清单](docs/DEFECT_REGISTER.md)
- [RC1 计划对照代码复查报告](docs/CODE_REVIEW_REPORT.md)
- [参赛项目报告内容基线](docs/PROJECT_REPORT.md)
- [技术说明与架构图](docs/TECHNICAL_GUIDE.md)
- [用户操作手册](docs/USER_GUIDE.md)
- [五分钟演示与降级手册](docs/DEMO_RUNBOOK.md)
- [参赛证据索引](docs/EVIDENCE_INDEX.md)
- [答辩问题库](docs/DEFENSE_QA.md)
- [开源依赖与许可清单](docs/OPEN_SOURCE_INVENTORY.md)
- [MIT 开源许可证](LICENSE)
- [版权声明](COPYRIGHT.md)
- [M12A 参赛材料内容基线验证记录](docs/M12A_VERIFICATION_REPORT.md)

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、ECharts、Lucide
- 后端：FastAPI、SQLAlchemy 2、Pydantic、Alembic、分层 MVC
- 本地数据库：SQLite
- 云端数据库：PostgreSQL，可迁移至华为云 RDS
- 缓存：Redis，可迁移至华为云 DCS
- 部署：Docker、Docker Compose、Linux 启动脚本

## 项目结构

```text
YunSync/
├── backend/app/
│   ├── controllers/     # HTTP 控制器
│   ├── services/        # 业务规则与用例
│   ├── repositories/    # 数据访问
│   ├── models/          # SQLAlchemy 数据模型
│   ├── schemas/         # 输入输出协议
│   ├── integrations/    # 华为云与缓存适配层
│   ├── core/            # 配置与安全常量
│   └── db/              # 数据库连接与初始化
├── frontend/src/
│   ├── views/           # 页面
│   ├── components/      # 通用组件
│   ├── stores/          # 前端状态
│   └── services/        # API 客户端
├── tests/               # 后端自动化测试
├── alembic.ini          # 数据库版本迁移配置
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── start.sh
└── start.ps1
```

## Windows 本地运行

```powershell
Copy-Item .env.example .env
.\start.ps1
```

也可以分开运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000

cd frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173`，API 文档位于 `http://localhost:8000/docs`。

## Linux 与华为 AI 开发者空间

推荐使用 Git 仓库同步代码；也可以上传不包含 `.venv`、`node_modules` 和 `.env` 的压缩包。

在 Windows 生成干净的上传包：

```powershell
.\scripts\package.ps1
```

生成文件位于 `release/YunSync-upload.zip`。

```bash
cd /root/workspace
git clone <your-repository-url> YunSync
cd YunSync
cp .env.example .env
chmod +x start.sh scripts/verify.sh
./start.sh
./scripts/verify.sh
```

`start.sh` 会安装 `requirements-dev.txt` 并用 `npm ci` 按锁文件初始化依赖。生产容器默认使用一次性 `migrate` 服务升级数据库，应用进程设置 `RUN_MIGRATIONS_ON_STARTUP=false`；可通过 `MIGRATION_DATABASE_URL` 为迁移任务使用独立数据库身份。

## 测试与构建

```powershell
.\.venv\Scripts\python.exe -m pytest
cd frontend
npm run typecheck
npm run build
```

Windows 下也可在项目根目录执行 `.\scripts\verify.ps1` 完成上述全部检查。

安全审计和本地 20 并发性能烟测分别执行：

```powershell
.\scripts\security_audit.ps1
.\.venv\Scripts\python.exe scripts\performance_smoke.py --base-url http://127.0.0.1:8000
```

RC1 合成主流程连续验收和本机 Edge 分辨率烟测分别执行：

```powershell
.\.venv\Scripts\python.exe scripts\rc1_acceptance.py --rounds 3
.\scripts\browser_smoke.ps1 -BaseUrl http://127.0.0.1:8000/start
```

参赛材料内容、必要章节和本地链接可以单独检查：

```powershell
.\.venv\Scripts\python.exe scripts\materials_check.py
```

云环境变量准备完成后，可先执行只读配置预检；PostgreSQL 备份和恢复工具的 dry-run 不连接数据库：

```powershell
.\.venv\Scripts\python.exe scripts\cloud_preflight.py --env-file .env
.\.venv\Scripts\python.exe scripts\postgres_ops.py backup --target backup\yunsync.dump --dry-run
```

## 华为云迁移

1. 将 `DATABASE_URL` 改为华为云 RDS PostgreSQL 连接串。
2. 将 `REDIS_URL` 改为华为云 DCS Redis 连接串。
3. 在 `backend/app/integrations/huawei/` 中替换 OCR、MaaS、OBS 的 Mock 实现。
4. 使用根目录 `Dockerfile` 构建镜像，在 ECS 或容器服务运行。
5. 通过环境变量或密钥管理服务注入凭据，不要上传 `.env`。

应用启动时会先执行 Alembic 迁移；仅在 `SEED_DEMO_DATA=true` 时幂等写入演示数据，Production 强制关闭该开关。正式生产环境建议把迁移步骤放入发布流水线，并保持单实例执行。

详细步骤见 `docs/HUAWEI_CLOUD_MIGRATION.md`。

## 版权与许可

Copyright © 2026 YunSync Contributors. 本项目依据 [MIT License](LICENSE) 开源，详细版权归属见 [COPYRIGHT.md](COPYRIGHT.md)。第三方依赖仍分别适用其原有许可证。
