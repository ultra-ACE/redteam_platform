# Docker 部署与仓库上传说明

本文件说明如何把项目上传到 Git 仓库，以及如何制作包含 Docker 镜像的离线发行包。

## 一、上传到仓库时上传什么

Git 仓库中建议提交：

- `backend/`：后端源码
- `frontend/`：前端源码
- `docker-compose.yml`：开发/默认 Compose 配置
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `.dockerignore` 文件
- `backend/scripts/`：seed、OpenAPI 导出等脚本
- `README.md`
- `README_DEPLOY.md`
- `openapi.yaml`
- 接口文档、设计文档

不要提交：

- `backend/.venv/`
- `backend/data/`
- `frontend/node_modules/`
- `frontend/dist/`
- `.npm-cache/`
- `*.tar`
- `*.tar.gz`
- `images/`
- `release/`
- 本地 `.env`
- 日志文件
- SQLite 数据库
- Docker 镜像文件

## 二、普通联网 Docker 部署

目标机器安装 Docker 后，在项目根目录执行：

```powershell
docker compose up --build -d
docker compose ps
```

初始数据：

```powershell
docker compose exec api python scripts/seed_demo.py
```

访问地址：

- 前端：http://127.0.0.1:5173
- 后端：http://127.0.0.1:8000
- Swagger：http://127.0.0.1:8000/docs

这种方式需要目标机器能够访问 Docker Hub、PyPI 和 npm registry。

## 三、推荐上传 Git 的协作方式

如果作者仓库是主仓库：

```powershell
git clone <author-repository-url>
cd <repository>
git checkout -b feature/docker-deployment
```

把本项目文件复制进去后：

```powershell
git status
git add .
git commit -m "feat: add full-stack docker deployment"
git push -u origin feature/docker-deployment
```

然后在 GitHub/GitLab 上发起 Pull Request。

如果你同时有自己的仓库和作者仓库：

```powershell
git remote add mine <your-repository-url>
git remote add author <author-repository-url>

git push mine feature/docker-deployment
```

只有在你拥有作者仓库写权限时，才直接推送到作者仓库：

```powershell
git push author feature/docker-deployment
```

否则不要直接推送到作者仓库的 `main`，应提交 Pull Request。

## 四、是否需要上传 Docker 镜像文件

一般不需要把 Docker 镜像提交到普通 Git 仓库。

原因是：

- 镜像 tar 通常几百 MB 到数 GB；
- Git 仓库会被永久撑大；
- 每次修改都产生新的二进制版本；
- GitHub 单文件通常有 100 MB 限制；
- 审计、拉取和克隆都会非常慢。

推荐策略：

| 场景 | 推荐方式 |
|---|---|
| 目标机器有网络 | 提交 Dockerfile + Compose，目标机器自己构建 |
| 需要 CI 自动构建 | GitHub Actions 构建并推送到 GHCR |
| 完全离线部署 | 把镜像 tar 放到 GitHub Release 或网盘 |
| 只做源码协作 | 只提交源码、Compose 和 Dockerfile |

## 五、制作离线 Docker 发行包

在能访问 Docker Hub 的机器上执行：

```powershell
docker compose build
docker pull postgres:16-alpine
docker pull redis:7-alpine

New-Item -ItemType Directory -Force release\images

docker save llm-eval-backend:local -o release\images\llm-eval-backend-amd64.tar
docker save llm-eval-frontend:local -o release\images\llm-eval-frontend-amd64.tar
docker save postgres:16-alpine -o release\images\postgres-16-alpine-amd64.tar
docker save redis:7-alpine -o release\images\redis-7-alpine-amd64.tar
```

把以下文件放入发行包：

```text
llm-eval-release/
├─ docker-compose.yml
├─ .env
├─ images/
│  ├─ llm-eval-backend-amd64.tar
│  ├─ llm-eval-frontend-amd64.tar
│  ├─ postgres-16-alpine-amd64.tar
│  └─ redis-7-alpine-amd64.tar
├─ scripts/
│  └─ load-images.ps1
└─ README_DEPLOY.md
```

目标机器执行：

```powershell
docker load -i images\llm-eval-backend-amd64.tar
docker load -i images\llm-eval-frontend-amd64.tar
docker load -i images\postgres-16-alpine-amd64.tar
docker load -i images\redis-7-alpine-amd64.tar

docker compose up -d
docker compose exec api python scripts/seed_demo.py
```

## 六、架构限制

镜像必须与目标机器 CPU 架构一致：

| 构建架构 | 目标架构 | 是否可用 |
|---|---|---|
| amd64 | amd64 | 可用 |
| arm64 | arm64 | 可用 |
| amd64 | arm64 | 通常不可用 |
| arm64 | amd64 | 通常不可用 |

如果要在 Apple M 系列、ARM Linux 和 Intel/AMD 机器之间通用，需要使用 Docker Buildx 构建多架构镜像，或者分别生成两套离线包。

## 七、README 是否需要单独生成

需要。

建议保留：

- `README.md`：项目介绍、开发启动、基本部署
- `README_DEPLOY.md`：Docker、离线发行包、仓库协作和目标机器部署

Docker 镜像 tar 不需要上传到普通 Git 仓库。若确实需要离线交付，应放到 GitHub Release、GitLab Release 或网盘，并在 README 中写明下载和加载命令。
