# 大模型越狱攻击安全评测系统

> Docker 离线发行包和 Git 上传说明见 `README_DEPLOY.md`。

面向本地环境的前后端分离大模型安全评测系统，包含 Benchmark 导入、风险分类、越狱攻击模板、评测任务、Judge 评价、规则校验、风险量化、人工复核、统计分析、报告导出和审计日志。

## Docker Compose 一键启动

在项目根目录执行：

```powershell
docker compose up --build -d
```

启动后访问：

| 服务 | 地址 |
|---|---|
| 前端 | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:8000 |
| Swagger | http://127.0.0.1:8000/docs |
| 健康检查 | http://127.0.0.1:8000/api/v1/health |

查看服务状态：

```powershell
docker compose ps
docker compose logs -f api worker frontend
```

停止服务：

```powershell
docker compose down
```

删除数据库和文件数据卷：

```powershell
docker compose down -v
```

Compose 会启动以下服务：

- PostgreSQL：业务数据库
- Redis：Celery Broker / Result Backend
- migrate：执行 Alembic 数据库迁移
- api：FastAPI 服务
- worker：Celery 后台评测 Worker
- frontend：Nginx 托管前端并代理 /api

## 本地非 Docker 启动

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

## OpenAPI

运行时 OpenAPI：

- http://127.0.0.1:8000/openapi.json

静态 YAML 由运行时 OpenAPI 导出：

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\export_openapi.py
```
