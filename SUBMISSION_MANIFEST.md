# 比赛作品提交清单

提交目标：只交付源码、依赖声明和启动配置，保证 Docker 与本地无 Docker 两种模式都能运行。

## 必须提交

根目录：

- `README.md`
- `README_DEPLOY.md`
- `docker-compose.yml`
- `dev-up.ps1`
- `openapi.yaml`

后端：

- `backend/app/`
- `backend/alembic/`
- `backend/alembic.ini`
- `backend/scripts/`
- `backend/tests/`
- `backend/requirements.txt`
- `backend/Dockerfile`
- `backend/README.md`
- `backend/.env.example`
- `backend/.dockerignore`
- `backend/docker-compose.yml`（兼容测试和备用启动）

前端：

- `frontend/src/`
- `frontend/public/`
- `frontend/index.html`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/vite.config.ts`
- `frontend/tsconfig.json`
- `frontend/tsconfig.app.json`
- `frontend/tsconfig.node.json`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `frontend/README.md`
- `frontend/.env.example`
- `frontend/.dockerignore`
- `frontend/.oxlintrc.json`

## 禁止提交

- `.git/`
- `backend/.venv/`
- `frontend/node_modules/`
- `frontend/dist/`
- `.pytest_cache/`、`__pycache__/`、`*.pyc`
- `backend/data/`
- `backend/backups/`
- 根目录 `backups/`
- `*.db`、`*.sqlite3`、`*.dump`、`*.sql`
- `.env`（只提交 `.env.example`）
- `*.log`
- `*.zip`、`*.tar`、`*.tar.gz`
- `交付物/`
- `benchmark_datasets/`
- `benchmark_datasets.zip`
- `report-*.html`
- 本地评测数据、数据库备份、模型密钥

## 两种启动方式

Docker：

```powershell
docker compose up --build -d
```

本地无 Docker：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd frontend
npm ci
npm run dev
```

无 Docker 模式还需要本机 Redis 和 Celery Worker；本地模型还需要 Ollama。

## 一键打包

```powershell
powershell -ExecutionPolicy Bypass -File .\package-submission.ps1
```

输出：

```text
release/redteam_platform_source.zip
```
