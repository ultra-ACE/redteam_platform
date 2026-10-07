# 大模型安全评测系统后端

本目录是基于 `../openapi.yaml` 生成的 FastAPI 后端骨架，当前已完成：

- FastAPI 路由骨架和 Pydantic Schema。
- SQLAlchemy 2.0 数据库连接和 29 张核心业务表。
- Alembic 迁移配置和初始迁移。
- Repository / Service / Unit of Work 分层骨架。
- 部分路由已接入 Service 和 UnitOfWork，用于示例和后续扩展。

## 目录结构

```text
backend/
  app/
    main.py                 FastAPI 入口
    core/config.py          环境配置
    db/
      base.py               SQLAlchemy Base 和命名规范
      session.py            引擎、Session、get_db
      models/               29 张表对应的 ORM Model
    repositories/
      base.py               通用 Repository
      domain.py             各领域 Repository
    services/
      base.py               Service 基类
      uow.py                UnitOfWork
      domain.py             领域 Service
    api/
      deps.py               UoW 依赖
      utils.py              统一响应和本地鉴权占位
      v1/routes/            接口路由
    schemas/                Pydantic Schema
  alembic/                  Alembic 迁移
  alembic.ini               Alembic 配置
  tests/                    pytest 测试
  requirements.txt
  .env.example
```

## 启动方式

在 `backend` 目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

打开：

- Swagger UI：<http://127.0.0.1:8000/docs>
- OpenAPI JSON：<http://127.0.0.1:8000/openapi.json>
- 健康检查：<http://127.0.0.1:8000/api/v1/health>

## 数据库

默认使用 SQLite：

```text
sqlite:///./data/app.db
```

切换到 PostgreSQL 时，设置：

```powershell
$env:DATABASE_URL="postgresql+psycopg://user:password@127.0.0.1:5432/llm_eval"
python -m alembic upgrade head
```

当前初始迁移使用 `Base.metadata.create_all` 创建 29 张表，适合本地 MVP 启动。数据库结构稳定后，建议改为显式 Alembic autogenerate 迁移。

## 分层约定

```text
Router -> Service -> UnitOfWork -> Repository -> SQLAlchemy Model -> Database
```

- Router：只处理 HTTP、依赖注入和响应模型。
- Service：组织业务流程、事务边界和领域逻辑。
- UnitOfWork：统一管理 Session 和 Repository。
- Repository：只做数据访问，不写业务判断。
- Model：只定义数据库结构。
- Schema：只定义请求、响应和校验规则。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

当前测试覆盖：

- 应用可导入。
- FastAPI OpenAPI 路径完整。
- 健康检查接口。
- 每个 OpenAPI 操作只有一个 tag。

## 下一步

1. 继续实现 29 张表对应的真实业务逻辑。
2. 增加模型适配器、模型健康检查和模型调用记录。
3. 接入 Redis + Celery，实现任务拆分、执行、重试和取消。
4. 实现 Judge、规则校验、风险量化和人工复核。
5. 实现报告生成、文件落盘、审计日志和错误追踪。
6. 将路由中的占位返回逐步替换为 Service 真实实现。

## 模型适配器

已实现统一适配器接口：

```text
app/adapters/
  base.py                ModelAdapter、GenerateRequest、GenerateResponse、HealthStatus
  openai_compatible.py   OpenAI-compatible / vLLM 等
  ollama.py              Ollama /api/generate
  custom_http.py         自定义 HTTP 模型服务
  mock.py                本地测试和联调
  factory.py             根据 ModelRegistry.adapter_type 构建适配器
```

模型配置中的 `secret_ref` 支持：

- `env:QWEN_API_KEY`：从环境变量读取，不落库明文。
- `literal:test-key`：仅用于本地测试，不建议用于真实密钥。
- 留空：适配器不发送 Authorization。

## Celery 任务队列

已实现：

```text
app/workers/
  celery_app.py   Celery 应用
  tasks.py        任务拆分、模型调用、Judge/规则/风险占位 Worker
  queue.py        入队封装，支持 eager 模式
```

任务链路：

```text
create/start task
  -> workers.dispatch_task
  -> workers.execute_task
     -> 展开 TaskCase
     -> workers.run_task_case
        -> 调用 ModelAdapter
        -> 写入 TaskAttempt
        -> 更新 TaskCase 和 EvaluationTask 进度
        -> 触发 Judge/规则/风险占位 Worker
```

### 使用 Redis 启动 Worker

先启动 Redis，然后执行：

```powershell
.\.venv\Scripts\python.exe -m celery -A app.workers.celery_app:celery_app worker -l info -P solo
```

Windows 下建议使用 `-P solo`。如果本机没有 Redis，可以先使用 eager 模式联调。

### 本地 eager 模式

修改 `.env`：

```text
CELERY_TASK_ALWAYS_EAGER=true
```

或者在 PowerShell 中临时设置：

```powershell
$env:CELERY_TASK_ALWAYS_EAGER="true"
```

eager 模式下，创建任务会同步执行模型调用，适合本地演示和测试。

### 使用 Docker Compose 启动 Redis / PostgreSQL

```powershell
docker compose up -d
```

默认服务：

- Redis：`127.0.0.1:6379`
- PostgreSQL：`127.0.0.1:5432`

如果要使用 PostgreSQL，设置：

```powershell
$env:DATABASE_URL="postgresql+psycopg://llm_eval:llm_eval@127.0.0.1:5432/llm_eval"
python -m alembic upgrade head
```

## 演示数据

运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.seed_demo
```

会创建：

- 一个统一风险体系。
- 一个 Demo Benchmark 和版本。
- 一条测试用例。
- 一个 `mock` 适配器模型。

之后可以用返回的 `benchmark_version_id` 和 `model_id` 在 Swagger 中创建评测任务。

## 评价链路

已实现：

```text
workers.run_task_case
  -> JudgeEvaluationService
  -> RuleValidationService
  -> RiskScoringService
  -> ManualReview 自动触发
```

新增服务：

- `JudgeEvaluationService`：规则 Judge、模型 Judge、JSON 解析和规则回退。
- `RuleValidationService`：关键词阻断、关键词放行、正则规则。
- `RiskScoringService`：Judge 可信度、六维风险分、风险等级、规则硬阈值和人工复核触发。
- `EvaluationResultService`：将 `task_attempts`、`judge_results`、`rule_validation_results`、`risk_assessments` 聚合为结果列表。

结果查询接口已经接入真实数据：

```text
GET /api/v1/evaluation-tasks/{task_id}/results
```

## 统计分析与报告生成

新增统计服务：

```text
app/services/statistics.py
```

统计接口：

```text
GET /api/v1/evaluation-tasks/{task_id}/statistics
GET /api/v1/evaluation-tasks/{task_id}/risk-summary
```

统计内容包括：

- 总结果数、安全数、不安全数、不确定数。
- 攻击成功率、平均风险分。
- Judge 平均可信度、人工复核率。
- 规则命中率。
- 风险等级分布。
- 风险类别分布。
- 模型对比。
- 攻击模板对比。
- 高风险案例 Top 10。

报告生成服务：

```text
app/services/reporting.py
```

支持格式：

- `json`
- `md`
- `html`
- `csv`
- `pdf`

报告生成流程：

```text
POST /reports
  -> 创建 Report 记录
  -> workers.generate_report
  -> 汇总 Statistics
  -> 汇总逐条评测结果
  -> 写入 data/reports/{report_id}/report-{report_id}.{ext}
  -> 写入 files 表
  -> 更新 Report 状态为 ready
GET /reports/{report_id}/download
  -> 下载生成的文件
```

PDF 使用 `reportlab` 和中文字体 `STSong-Light` 生成。

## 报告模板与自动报告

新增数据表：

- `report_templates`
- `report_template_versions`

新增接口：

```text
GET  /api/v1/report-templates
POST /api/v1/report-templates
GET  /api/v1/report-templates/{template_id}/versions
POST /api/v1/report-templates/{template_id}/versions
GET  /api/v1/report-template-versions/{version_id}
POST /api/v1/report-template-versions/{version_id}/publish
```

`POST /api/v1/reports` 的请求体新增：

```json
{
  "template_version_id": 1
}
```

当 `template_version_id` 存在时，报告会使用该模板版本渲染 JSON、Markdown、HTML 或 CSV。PDF 仍使用内置报告生成器。

自动报告：

```text
模型调用
  -> Judge
  -> 规则校验
  -> 风险量化
  -> 检查任务是否全部完成
  -> 自动创建 report_type=auto 的报告
  -> 生成并保存报告
```

自动报告默认格式为 `pdf`，也可以通过任务 `config.auto_report_format` 指定为 `json`、`md`、`html` 或 `csv`。

## 风险分类与映射

后端已实现：

- 风险体系查询和创建。
- 风险分类树查询和创建。
- Benchmark 原始标签映射。
- 未映射标签查询。
- 映射完成后自动更新测试用例风险标签。
- 单次模型调用风险详情查询。

前端页面：

- `/risk-taxonomy`
- 左侧：风险体系列表。
- 中间：风险分类树。
- 右侧：Benchmark 版本映射进度。
- 下方：原始标签映射表，可为未映射标签选择统一风险类别并保存。

## 攻击方法与攻击模板

后端已实现：

- 攻击方法查询、创建、修改、停用。
- 攻击模板查询、创建、修改、停用。
- 模板变量检测与校验。
- 模板预览和变量渲染。
- 模板版本列表、新版本创建、版本发布。

前端页面：

- `/attack-templates`
- 攻击方法列表和管理。
- 攻击模板列表和管理。
- 模板变量标签展示。
- 预览弹窗：检测变量、缺失变量、未使用变量、未声明变量。
- 版本管理：查看版本、创建新版本、发布版本。

## Judge 配置管理

后端已实现：

- Judge Profile 查询、创建、详情、修改、停用。
- Judge 模型绑定和参数配置。
- Judge 可信度统计。
- Judge 结果重新评价。

前端页面：

- `/judge`
- Judge 配置列表。
- 新建和编辑 Judge。
- Judge 类型、模型、策略、Prompt 模板和参数配置。
- Judge 可信度查询。
- Judge 结果重新评价。

## 人工复核管理

后端已实现：

- 待复核队列查询。
- 复核详情查询。
- 复核结果提交。
- 复核记录更新。
- 复核历史查询。
- 修正风险类别。
- 修正风险分并重新计算风险等级。
- 复核结论：确认、修正、驳回、暂不处理。

前端页面：

- `/reviews`
- 待复核队列。
- 复核历史。
- 复核详情。
- 模型 Prompt 和输出查看。
- Judge、规则和风险信息查看。
- 风险类别和风险分修正。


## Docker Compose 全栈启动

推荐从项目根目录执行：

```powershell
docker compose up --build -d
```

该方式会同时启动 PostgreSQL、Redis、Alembic 迁移、FastAPI API、Celery Worker 和前端 Nginx 服务。

如果从 backend 目录执行，可使用本目录下的 `docker-compose.yml`，它会以 `../frontend` 作为前端构建上下文。
