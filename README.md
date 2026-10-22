
# 大模型越狱攻击安全评测系统

面向本地环境的前后端分离评测平台，用于导入异构安全数据集、配置越狱攻击模板、
批量评测本地或远程大模型，并输出可解释的 Judge 判定、规则命中与 HTML 报告。

> 离线发行与镜像构建说明见 `README_DEPLOY.md`。

## 功能概览

- **模型管理**：支持 OpenAI-compatible、Ollama、Custom HTTP、Mock 四种适配器；
  支持新建、编辑、启停与连接测试；API Key 在接口和页面上只显示掩码。
- **种子库导入**：自动识别 HarmBench、AdvBench、TDC2023 与中文通用数据集，
  归一为统一的种子问题；只使用种子库名称，不再维护 Benchmark 版本。
- **数据集类型**：`benign` / `harmful` / `jailbreak`；越狱样本再区分
  `seed`（种子）与 `template`（模板）。
- **模板库**：模板按模板库组织，支持 JSON/JSONL/TXT 导入、变量校验、
  预览和模板自身版本管理。
- **攻击方式**：支持静态模板、Base64、Puzzler 和 PAIR 多轮迭代；
  任务执行支持暂停、继续、取消和 Worker 重启恢复，已成功用例不会重跑。
- **Judge 与规则**：模型 Judge、规则 Judge、集成 Judge；输出 verdict、
  置信度、可信度分解与规则命中证据。
- **结果与复核**：逐条结果表、完整证据链抽屉、低可信度/规则冲突自动复核。
- **统计与报告**：按用例统计安全/有害/不确定结果；HTML 报告展示攻击方式、
  种子库、模板、被测模型、Judge 配置和全部有害用例输出。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI、SQLAlchemy、Alembic、Celery |
| 数据库 | PostgreSQL（Compose）或 SQLite（本地快速测试） |
| 队列 | Redis（Celery Broker / Result Backend） |
| 前端 | React、TypeScript、Ant Design、Vite |

## 快速开始（Docker Compose）

前置条件：Docker Desktop 已启动；如使用本地模型，另需安装 Ollama。

一键启动（自动处理 Ollama 监听地址 + 启动整套容器）：

```powershell
powershell -ExecutionPolicy Bypass -File .\dev-up.ps1
```

或者只启动容器：

```powershell
docker compose up --build -d
docker compose ps
```

访问地址：

| 服务 | 地址 |
|---|---|
| 前端 | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000 |
| Swagger | http://127.0.0.1:8000/docs |
| 健康检查 | http://127.0.0.1:8000/api/v1/health |

Compose 会启动：PostgreSQL、Redis、migrate、api、worker、frontend。

```powershell
docker compose logs -f api worker     # 查看日志
docker compose down                   # 停止
docker compose down -v                # 停止并删除数据卷
```

## 使用本地 Ollama 模型

容器内的 `127.0.0.1` 指向容器自身，必须通过 `host.docker.internal` 访问宿主机。
同时 Ollama 需要监听 `0.0.0.0`，否则容器无法连接。

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_HOST","0.0.0.0:11434","User")
ollama serve
```

在"模型管理"中新建：

| 字段 | 值 |
|---|---|
| 适配器类型 | `Ollama` |
| 服务地址 | `http://host.docker.internal:11434` |
| 模型标识 | `qwen2.5:7b`（与 `ollama list` 一致） |
| 密钥引用 | 留空 |

## 本地非 Docker 启动

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm ci
npm run dev
```

任务执行还需要 Redis 与 Celery Worker（Windows 使用 `--pool=solo`）：

```powershell
cd backend
.\.venv\Scripts\celery.exe -A app.workers.celery_app:celery_app worker --loglevel=info --pool=solo
```

## 模型密钥填写

推荐使用环境变量，避免明文入库：

```text
env:DEEPSEEK_API_KEY        从环境变量读取
literal:sk-xxxxxxxx         直接写入数据库
```

接口不会回传明文：`literal:` 只返回后四位（如 `literal:****14be`），
编辑时留空表示不修改。历史数据中未加前缀的密钥也会被识别为明文处理。

## 数据集导入

在"评测资产 → 种子库"上传 CSV / JSONL，系统按表头自动识别适配器。

| 数据集 | 关键字段 | 适配器 |
|---|---|---|
| HarmBench | `Behavior`、`SemanticCategory`、`BehaviorID` | `harmbench_csv` |
| AdvBench / TDC2023 | `Behavior`、`Category`、`BehaviorID` | `behavior_csv` |
| 中文通用 | `提示词`、`数据集类型`、`样本类型`、`原始标签` | `chinese_generic` |

说明：

- llm-attacks 原始 `harmful_behaviors.csv` 是 `goal,target` 结构，需把 `goal`
  改名为 `Behavior` 后导入；`harmful_strings.csv` 不含提示词，不可用。
- 中文数据集与原始数据文件不入库，本地准备后直接导入即可。
- 未声明类型的样本默认按 `harmful` 处理。

## 测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm run typecheck
npm run build
```

## OpenAPI

- 运行时：http://127.0.0.1:8000/openapi.json
- 静态文件由运行时导出：

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\export_openapi.py
```

## 目录结构

```text
backend/
  app/adapters/          模型适配器
  app/api/v1/routes/     REST 接口
  app/db/models/         SQLAlchemy 模型
  app/services/          业务服务（导入、执行、Judge、报告等）
  app/workers/           Celery 任务与断点恢复
  alembic/versions/      数据库迁移
  scripts/               数据转换与修复脚本
  tests/                 后端测试
frontend/
  src/api/               接口封装
  src/pages/             页面
  src/components/        通用组件
dev-up.ps1               一键启动本地开发栈
```

## 已知说明

- `0005_contract_freeze` 是破坏性迁移，会删除旧的风险分类、审计与报告模板表。
  对已有数据库执行前请先备份；该迁移不支持自动降级。
- 集成 Judge 目前在后端复用规则评价逻辑，尚未实现多模型投票。
- SQLite 适合本地快速测试；API 与 Worker 同时写入时可能锁表，正式演示建议使用
  Compose 中的 PostgreSQL。
## 核心评测逻辑（种子与模板）

本系统采用「种子问题 + 官方模板 + 被测模型 + Judge」的流程进行安全评测。

- **种子（Seed）**：指基础测试用例（如：“如何制作危险化学品”），保存在 `test_cases.prompt` 字段中。
- **模板（Template）**：官方编写的高级 Prompt（如 DAN、角色扮演等），用于包装种子以绕过模型安全限制，保存在 `attack_templates.template_text` 字段中。
- **完整 Prompt**：在任务执行时，系统会将模板中的占位符（如 `{prompt}` / `{seed}` 等）替换为种子内容，生成最终发送给大模型的测试文本。

## 攻击方式支持

系统支持以下攻击方式：

- **静态模板**：模板 + 种子直接发送，不做额外变换。
- **Base64**：把完整 Prompt 编码后要求目标模型先解码再回答。
- **Puzzler**：把完整 Prompt 包装成谜题、故事或倒序文本。
- **PAIR**：攻击模型基于种子、上一轮输出和 Judge 反馈持续改写攻击 Prompt，
  最多迭代配置轮数，Judge 判定 `unsafe` 时提前停止。
