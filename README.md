# ScholarMind

ScholarMind 是面向科研与学术场景的「私有文献知识库 + RAG 检索对话」一体化单仓：用户可创建知识库、上传 PDF 文献，由后端完成解析与切块，并写入向量与全文关键词索引，在对话页中基于检索证据获得可核对、可流式呈现的回答。工程上前端采用 React（Vite、Tailwind），后端采用 FastAPI，覆盖账户与知识库、文献生命周期、索引构建与对接外部推理的 SSE 链路等核心纵向能力；Agent 编排、MCP 工具、评估看板与报告导出等将按产品规划迭代接入。功能边界、里程碑与落地步骤以根目录 PRD（`ScholarMind_PRD_v1.0`）及 **[开发流程与步骤](docs/ScholarMind_开发流程与步骤_v1.md)** 为准。

---

## 项目背景

| 维度 | 说明 |
|------|------|
| **产品目标** | 研究问题 → 私有 RAG（可选公开 MCP）→ 可核对、结构化的回答与报告线索 |
| **典型用户** | 需要管理论文/笔记、希望对「自己的材料」提问并得到带依据回答的研究者或团队 |
| **技术原则（PRD）** | FastAPI、异步任务、向量检索 + BM25、MCP、后续 LangGraph 编排等；关系型库采用 **MySQL** |
| **当前阶段** | 已完成 **账户与知识库、文献上传与解析入库、基于知识库的流式对话（EdgeFN）** 等 P0 闭环的大部分「纵向切片」；Agent 全链路、MCP、评估看板、报告导出等仍为规划或占位 |

---

## 仓库结构

| 目录 | 说明 |
|------|------|
| `scholarmind-server/` | **FastAPI** 后端：JWT 鉴权、知识库与文献 CRUD、PDF 入库与解析任务、Chroma + Whoosh 索引、对接 EdgeFN 的 **SSE 流式对话** |
| `scholarmind-web/` | **React + Vite + Tailwind** 前端：登录、知识库、文献列表、对话页（Streamdown 流式 Markdown + Shiki 代码高亮）等 |
| `docs/` | 工程文档：开发流程与 PRD 阶段映射、**[对话记忆与上下文技术方案](docs/ScholarMind_对话记忆与上下文技术方案_v1.md)**（MySQL / Redis / 向量库 / 摘要与默认参数 / Prompt KV 缓存）等 |

其他 PRD 中规划的目录（如独立 Agent 服务、MCP 包、评估流水线）若在仓库中出现，以各子目录 README 或代码注释为准逐步接线。

---

## 已实现能力（截至当前代码）

### 后端（`scholarmind-server`）

- **健康检查**：`GET /api/v1/health`
- **用户**：邮箱注册 / 登录，**JWT** 访问令牌
- **知识库**：创建、列表、数量上限等（多租户按用户隔离）
- **文献**：PDF 上传、列表、状态（pending / processing / done / failed）、失败重试；本地存储抽象，便于后续换 OSS
- **解析流水线**：PDF 文本抽取 → 切块 → **嵌入**（支持 `EMBEDDING_MODE`：`bge` 本地、`http` 云端 OpenAI 兼容 embeddings、`hash` 测试）→ **Chroma** 向量写入 + **Whoosh** 关键词索引
- **对话**：`POST /api/v1/chat/stream`，**SSE** 推送 `trace_id`、`thinking_delta`（若上游提供推理字段）、`delta`、`done`；系统提示中可注入所选知识库的 **检索摘录**（RAG 上下文）
- **任务执行**：支持 **Celery + Redis** 或本机 **`INGEST_BACKGROUND_THREAD=true` + FastAPI BackgroundTasks**（便于无 Worker 时开发）

### 前端（`scholarmind-web`）

- **路由**：`/login`、`/chat`、`/knowledge-bases`、`/documents`、`/reports`、`/evaluation`、`/tools`、`/settings` 等（部分页面为占位或后续迭代）
- **对话页**：对接后端 SSE；**思维链** 与正文中的 `<think>` / `<think>` 等标签做拆分展示；正文使用 **[Streamdown](https://streamdown.ai/)** + `@streamdown/code`（**Shiki** 语法高亮）与 `@streamdown/cjk`（中文排版）

### 尚未完成或仅占位（与 PRD 对齐的预期）

- **LangGraph** 深度编排、**MCP** 工具链、执行过程 SSE 面板与完整 **溯源/导出**
- **Milvus** 生产集群策略、**Rerank**、RAGAS 评估流水线与真实看板数据
- **Google OAuth**、对象存储生产切换等（见 `docs/ScholarMind_开发流程与步骤_v1.md`）

---

## 快速开始

### 1. 准备环境

- **MySQL 8.x**：创建数据库与用户，配置连接串
- **Redis**（若使用 Celery Worker 而非纯本机后台任务）：默认 `redis://127.0.0.1:6379/0`
- **EdgeFN（或兼容 OpenAI 的网关）**：用于对话与（可选）云端向量 `embeddings`

### 2. 后端

```bash
cd scholarmind-server
cp env.example .env
# 编辑 .env：DATABASE_URL、JWT_SECRET、EDGEFN_API_KEY 等

uv sync
uv run alembic upgrade head   # 若已配置迁移
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API 文档：<http://127.0.0.1:8000/docs>
- 本机**不跑 Celery** 时：在 `.env` 中设置 `INGEST_BACKGROUND_THREAD=true`，并阅读 `env.example` 中关于 `EMBEDDING_MODE` 的说明（云端嵌入可避免本机下载大模型）

### 3. 前端

```bash
cd scholarmind-web
pnpm install   # 或 npm install
pnpm dev       # 默认与 Vite 开发服务器端口一致，请按控制台提示访问
```

开发环境下，前端通过 **`vite.config.ts` 中的 `server.proxy`** 将 `/api` 转发到 `http://127.0.0.1:8000`，与后端默认端口一致即可；生产部署时需自行配置同源反向代理或改写请求基地址。

### 4. 代码块高亮（前端）

助手回复需使用 **带语言的 fenced code**（例如 ` ```typescript `），并确保已引入 `streamdown/styles.css`（本仓库在 `scholarmind-web/src/index.css` 中已 `@import`）。Shiki 会按需加载高亮资源；若高亮不生效，请检查浏览器控制台网络错误与是否使用了正确的语言标识。

---

## 主要环境变量（后端）

完整说明见 **`scholarmind-server/env.example`**。常用项包括：

| 变量 | 作用 |
|------|------|
| `DATABASE_URL` | MySQL 异步连接（`mysql+asyncmy://...`） |
| `JWT_SECRET` | 签发 JWT 的密钥 |
| `STORAGE_LOCAL_ROOT` | 上传文件本地根路径 |
| `CHROMA_DATA_PATH` / `WHOOSH_INDEX_ROOT` | 向量与全文索引目录 |
| `EDGEFN_API_KEY` / `EDGEFN_API_BASE_URL` / `EDGEFN_CHAT_MODEL` | 对话模型网关 |
| `EMBEDDING_MODE` | `bge` \| `http` \| `hash`；`http` 时可与 EdgeFN 共用 base/key |
| `INGEST_BACKGROUND_THREAD` | `true` 时在本进程内异步解析（开发友好） |

**切勿**将真实 `.env` 或密钥提交到版本库。

---

## 测试与质量

```bash
cd scholarmind-server
uv sync --dev
uv run pytest tests/ -q
```

前端：`pnpm run build` 做 TypeScript 与生产构建校验。

---

## 相关文档

- [ScholarMind 开发流程与步骤 v1.2](docs/ScholarMind_开发流程与步骤_v1.md) — 与 PRD 模块、里程碑、技术选型的映射
- [scholarmind-server README](scholarmind-server/README.md) — 服务端补充说明（若与本文冲突，以根目录本文与 `env.example` 为准）

---

## 许可证与贡献

许可证以各子包声明为准；贡献前请阅读 PRD 与 `docs/` 下的流程文档，保持 **纵向切片** 与里程碑对齐。
