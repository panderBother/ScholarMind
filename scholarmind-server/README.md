# scholarmind-server

FastAPI 服务：对外 REST/WebSocket，对内调用 `scholarmind-agent` 与 Celery Worker。

## 本地运行

```bash
cd scholarmind-server
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

健康检查：`GET http://127.0.0.1:8000/api/v1/health`

## 数据库迁移

配置 `DATABASE_URL` 后执行（优先使用虚拟环境里的 CLI，避免 PowerShell 找不到 `alembic`）：

```bash
# Windows（未激活 venv 时）
.\.venv\Scripts\alembic.exe upgrade head

# 已激活 .venv 或 Unix
alembic upgrade head
```

含对话记忆表：`003_conversations_chat`（`conversations`、`chat_messages`、`conversation_summaries`）。

## 对话记忆（多轮）

- 流式：`POST /api/v1/chat/stream` 在单连接内持有 DB 会话；请求体可选 `conversation_id`，首次为空则 SSE 会下发 `conversation_id` 事件。
- 会话 CRUD：`POST/GET /api/v1/conversations`、`GET /api/v1/conversations/{id}/messages`、`DELETE ...`。
- 后置任务：`scholarmind.chat_memory.after_turn`（Celery；`CELERY_TASK_ALWAYS_EAGER=true` 时在 API 进程内同步执行），负责 Chroma 对话向量写入与周期摘要。
