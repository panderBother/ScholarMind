# KnowMind Docker 部署

用手动 `uvicorn` 终端跑后端，SSH 断开或进程崩溃就会挂。推荐用 **Docker Compose**：`restart: always`、健康检查、启动时自动迁移。

## 对比

| 方式 | 优点 | 缺点 |
|------|------|------|
| 终端 `uvicorn` | 简单 | 断连即挂、无自动重启 |
| systemd | 可自动重启 | 要自己写 unit、配 Nginx |
| **Docker Compose** | 一键起 MySQL/Redis/API/前端、隔离、易备份卷 | 需装 Docker |

## 前置

- Linux 服务器已装 [Docker](https://docs.docker.com/engine/install/) 与 Compose 插件（`docker compose version`）
- 代码在 `/opt/KnowMind`（`git clone` 或同步均可）

## 快速开始

```bash
cd /opt/KnowMind

# 1. 环境变量（密码、JWT、模型 Key）
cp .env.docker.example .env.docker
nano .env.docker

# 2. 可选：保留 knowmind-server/.env 里其它项；compose 会覆盖 DATABASE_URL 等
cp knowmind-server/env.example knowmind-server/.env

# 3. 构建并后台启动（首次较慢：拉镜像 + 装 Python 依赖）
docker compose --env-file .env.docker up -d --build

# 4. 看 API 是否就绪
docker compose logs -f api
curl -s http://127.0.0.1/api/v1/health
```

浏览器访问：`http://服务器IP/`（默认映射 **80** 端口，由 `web` 容器 Nginx 提供前端并反代 `/api`）。

## 服务说明

| 服务 | 作用 |
|------|------|
| `mysql` | 数据库，数据在卷 `mysql-data` |
| `redis` | Celery / 队列（默认已启） |
| `api` | FastAPI；启动时 `alembic upgrade head` |
| `web` | 前端静态 + Nginx 反代 API |
| `worker` | 可选，见下方 Celery |

持久化目录（上传、Chroma、Whoosh）在卷 **`knowmind-data`** → 容器内 `/app/knowmind-server/data`。

## 文档解析：两种模式

**默认（推荐入门）**：`.env.docker` 里 `INGEST_BACKGROUND_THREAD=true`  
→ 只起 `api`，解析在 API 进程内后台线程，**不必**起 `worker`。

**Celery（生产更重负载）**：

```bash
# .env.docker
INGEST_BACKGROUND_THREAD=false

docker compose --env-file .env.docker --profile celery up -d --build
```

会额外启动 `worker` 容器。

## 常用命令

```bash
cd /opt/KnowMind

# 查看状态
docker compose ps

# 重启 API（改代码后）
docker compose --env-file .env.docker up -d --build api

# 只看日志
docker compose logs -f api web

# 停止（保留数据卷）
docker compose down

# 停止并删库（慎用）
docker compose down -v
```

## 更新版本

```bash
cd /opt/KnowMind
git pull
docker compose --env-file .env.docker up -d --build
```

前端变更会重建 `web`；后端变更会重建 `api`。迁移在 `api` 启动时自动执行。

## 与旧版「裸机 Nginx」共存

若仍想用 `/etc/nginx/sites-available/knowmind`：

- 可只跑 `mysql` + `redis` + `api`：`docker compose up -d mysql redis api`
- Nginx `proxy_pass` 指到 `http://127.0.0.1:8000`（把 `api` 的 8000 映射出来：`ports: ["8000:8000"]`）

更简单是**关掉宿主机 Nginx 80**，只用 compose 里的 `web` 服务。

## 环境变量要点

`.env.docker` 中务必修改：

- `MYSQL_ROOT_PASSWORD` / `MYSQL_PASSWORD`
- `JWT_SECRET`
- `EDGEFN_API_KEY`（对话）
- Docker 内建议 `EMBEDDING_MODE=http`，避免首次下载 BGE 模型占满磁盘

`DATABASE_URL` 由 compose 写死为 `mysql:3306`，**不要**再指向 `127.0.0.1`。

## 故障排查

```bash
# API 起不来
docker compose logs api --tail 100

# 进 MySQL
docker compose exec mysql mysql -u knowmind -p knowmind

# 进 API 容器
docker compose exec api bash
```

分类「未分类」入库 404：需包含后端 `list_category_tree` 的 commit 修复，更新镜像后 `docker compose up -d --build api`。

## 资源建议

- 内存：≥ 4GB（若 `EMBEDDING_MODE=bge` 本机嵌入需更多）
- 磁盘：模型与上传文件会增长，定期备份 `mysql-data` 与 `knowmind-data` 卷
