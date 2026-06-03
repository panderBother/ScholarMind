# knowmind-server

KnowMind 后端服务，基于 **FastAPI**：提供 REST API 与 SSE 流式对话，负责鉴权、知识库与文档管理、Hybrid RAG 检索、报告生成、MCP 工具编排，以及 Celery / 后台线程异步解析任务。

---

## 已实现 API 模块

| 前缀 | 功能 |
|------|------|
| `/auth` | 邮箱注册 / 登录、Refresh 续期 |
| `/knowledge-bases` | 知识库 CRUD、文档上传 / 预览 / 删除、条目与分类、URL 采集、对话提炼 |
| `/conversations` | 多轮会话 CRUD 与历史消息 |
| `/chat` | RAG 问答（含 `/stream` SSE）、深度研究、反馈 |
| `/chat/attachments` | 对话附件上传 |
| `/reports` | 报告生成与 Markdown / PDF 导出 |
| `/experts` | 领域专家流式对话 |
| `/mcp/tools` | MCP 工具配置与开关 |
| `/evaluation` | RAG 评估报告读取与触发 |
| `/workspace/files` | 本地文件读写（MCP 配套） |
| `/health` | 健康检查 |

完整接口见启动后的 Swagger：<http://127.0.0.1:8000/docs>

---

## 快速开始

### 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（推荐）
- MySQL 8.x（需提前建库）
- Redis（Celery 模式需要；可用 `docker compose -f docker-compose.redis.yml up -d` 启动）
- EdgeFN 或兼容 OpenAI 的模型网关（`.env` 中配置 `EDGEFN_*`）

### 安装与启动

```bash
cd knowmind-server
cp env.example .env
# 编辑 .env：DATABASE_URL、JWT_SECRET、EDGEFN_API_KEY 等

uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：`GET http://127.0.0.1:8000/api/v1/health`

### 解析任务模式

| 模式 | 配置 | 说明 |
|------|------|------|
| 后台线程（开发推荐） | `INGEST_BACKGROUND_THREAD=true` | 无需 Celery，解析在 API 进程内异步执行 |
| Celery Worker | 默认 | 另开终端：`uv run celery -A app.workers.celery_app worker -l info`，与 API 共用 `.env` |

---

## 数据库迁移

配置 `DATABASE_URL` 后执行：

```bash
uv run alembic upgrade head
```

Windows 若未使用 uv，也可直接调用虚拟环境内的 CLI：

```bash
.\.venv\Scripts\alembic.exe upgrade head
```

---

## 对话记忆（多轮）

- 流式：`POST /api/v1/chat/stream` 在单连接内持有 DB 会话；请求体可选 `conversation_id`，首次为空时 SSE 会下发 `conversation_id` 事件。
- 会话 CRUD：`POST/GET /api/v1/conversations`、`GET /api/v1/conversations/{id}/messages`、`DELETE ...`。
- 后置任务：`knowmind.chat_memory.after_turn`（Celery；`CELERY_TASK_ALWAYS_EAGER=true` 时在 API 进程内同步执行），负责 Chroma 对话向量写入与周期摘要。

---

## 主要环境变量

完整列表见 [`env.example`](env.example)。常用项：

| 变量 | 作用 |
|------|------|
| `DATABASE_URL` | MySQL 异步连接 |
| `JWT_SECRET` | JWT 签发密钥 |
| `STORAGE_LOCAL_ROOT` | 上传文件本地根路径 |
| `CHROMA_DATA_PATH` / `WHOOSH_INDEX_ROOT` | 向量与全文索引目录 |
| `EDGEFN_API_KEY` / `EDGEFN_CHAT_MODEL` | 对话模型网关 |
| `EMBEDDING_MODE` | `bge` \| `http` \| `hash` |
| `INGEST_BACKGROUND_THREAD` | 本进程内异步解析 |
| `REDIS_URL` / `CELERY_TASK_ALWAYS_EAGER` | Celery 任务队列 |

---

## 测试

```bash
uv sync --dev
uv run pytest tests/ -q
```

---

## 相关文档

- [项目根 README](../README.md)
- [对话记忆与上下文技术方案](../docs/KnowMind_对话记忆与上下文技术方案_v1.md)
