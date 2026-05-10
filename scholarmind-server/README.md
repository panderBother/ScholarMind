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
