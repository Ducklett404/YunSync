# YunSync 云循 HealthLoop

云循是面向体重与代谢健康管理的 AI 个人健康行为优化平台。首版完成“合成体检报告解析、候选行动比较、14 天个人微实验、每日记录、探索性结果展示”的闭环。

> 本项目仅用于健康教育、自我监测和生活方式支持，不提供疾病诊断、治疗或药物调整意见。仓库中的人物与健康数据均为合成数据。

## 项目文档

- [从 0 开始的详细开发计划书](docs/DEVELOPMENT_PLAN.md)
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
- [行动模板登记表](docs/ACTION_TEMPLATE_REGISTER.md)
- [M5A 行动模板治理、透明排序与解释安全守卫验证记录](docs/M5A_VERIFICATION_REPORT.md)
- [M6A 14 天实验状态机与锁定日程验证记录](docs/M6A_VERIFICATION_REPORT.md)
- [M7A 每日记录、应用内提醒与数据导入验证记录](docs/M7A_VERIFICATION_REPORT.md)
- [华为云迁移说明](docs/HUAWEI_CLOUD_MIGRATION.md)

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
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
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
chmod +x start.sh
./start.sh
```

## 测试与构建

```powershell
.\.venv\Scripts\python.exe -m pytest
cd frontend
npm run typecheck
npm run build
```

Windows 下也可在项目根目录执行 `.\scripts\verify.ps1` 完成上述全部检查。

## 华为云迁移

1. 将 `DATABASE_URL` 改为华为云 RDS PostgreSQL 连接串。
2. 将 `REDIS_URL` 改为华为云 DCS Redis 连接串。
3. 在 `backend/app/integrations/huawei/` 中替换 OCR、MaaS、OBS 的 Mock 实现。
4. 使用根目录 `Dockerfile` 构建镜像，在 ECS 或容器服务运行。
5. 通过环境变量或密钥管理服务注入凭据，不要上传 `.env`。

应用启动时会先执行 Alembic 迁移，再幂等写入演示数据。正式生产环境建议把迁移步骤放入发布流水线，并保持单实例执行。

详细步骤见 `docs/HUAWEI_CLOUD_MIGRATION.md`。
