# ScholarMind

**ScholarMind** 是面向科研与学术场景的 **AI Native 私有知识库平台**：用户注册登录后，可创建多个知识库、上传 PDF 文献并完成自动解析与索引，在对话页基于所选知识库进行 **Hybrid RAG 检索增强问答**，并将对话提炼为结构化条目、生成研究报告。工程上采用 **React（Vite + Tailwind）+ FastAPI** 单仓架构，覆盖账户鉴权、知识库与文献生命周期、向量 + 全文双索引、SSE 流式对话、MCP 工具集成等核心能力。

> 功能边界、里程碑与验收标准以 **[PRD v2.0](docs/ScholarMind_PRD_v2.0.md)**（[`ScholarMind_PRD_v2.0.docx`](docs/ScholarMind_PRD_v2.0.docx)）及 **[开发流程与步骤](docs/ScholarMind_开发流程与步骤_v1.md)** 为准。

---

## 界面预览

> 在 Cursor / VS Code 中请用 **Markdown 预览** 查看截图：`Ctrl+Shift+V`（Mac：`Cmd+Shift+V`），或右上角点击预览图标。源码模式下只会看到路径，不会渲染图片。

### 对话与研究

基于所选知识库的 RAG 流式问答；支持会话历史、深度研究 / 联网搜索 / 文件读写开关，以及「提炼到知识库」「生成报告」等快捷操作。

![对话与研究](./assets/01-chat-research.png)

### 知识库

按课题创建与管理多个私有知识库，展示文献数量、存储与更新时间；支持创建、重命名与删除。

![知识库](./assets/02-knowledge-bases.png)

### 文献管理 · 文献视图

选择目标知识库上传 PDF（单文件 ≤ 50MB，单次最多 20 个），查看解析状态（pending → processing → done / failed），失败可重试；支持 Celery 异步解析或本机后台线程模式。

![文献视图](./assets/03-documents-pdf.png)

### 文献管理 · 条目视图

除 PDF 原文外，还可管理从对话提炼、URL 采集等来源的 **知识条目**（草稿 / 已发布 / 已归档），支持预览、编辑与删除。

![条目视图](./assets/04-documents-entries.png)

### 报告

由对话一键生成结构化研究报告，展示摘要与引用数量，可打开详情或删除。

![报告](./assets/05-reports.png)

### 评估看板

RAGAS 指标（忠实度、答案相关性、上下文召回 / 精准）趋势与版本对比；当前为 **UI 示意**，真实数据待评估流水线接入。

![评估看板](./assets/06-evaluation-dashboard.png)

### 工具与集成

内置 MCP 工具开关（联网搜索、本地文件读写等），并支持从 Cursor / Claude 等环境导入外部 `mcp.json` 配置。

![工具与集成](./assets/07-tools-mcp.png)

---

## 产品定位

| 维度 | 说明 |
|------|------|
| **产品目标** | 研究问题 → 私有 RAG（可选 MCP 扩展）→ 可核对、结构化的回答与报告 |
| **典型用户** | 需要管理论文 / 笔记、希望对「自己的材料」提问并得到带依据回答的研究者或团队 |
| **技术原则** | FastAPI、异步任务、Chroma 向量 + Whoosh BM25、MCP、MySQL 多租户隔离 |
| **当前阶段** | P0 纵向切片已基本贯通：账户 → 知识库 → 文献入库 → 对话 RAG → 条目 / 报告；评估流水线与 LangGraph 深度编排仍在迭代 |

---

## 典型工作流

```mermaid
flowchart LR
  A[注册 / 登录] --> B[创建知识库]
  B --> C[上传 PDF / 采集 URL]
  C --> D[异步解析与双索引]
  D --> E[对话页选择知识库提问]
  E --> F[流式 RAG 回答]
  F --> G[提炼条目 / 生成报告]
  G --> H[条目发布后可被检索引用]
```

1. **入库**：PDF 上传后由 Worker 抽取文本、切块、Embedding，写入 Chroma + Whoosh。
2. **问答**：对话页选定知识库，后端检索相关片段注入 Prompt，SSE 流式返回。
3. **沉淀**：对话结果可提炼为知识条目，或一键生成带引用的研究报告。
4. **扩展**：在「工具与集成」中启用联网搜索、文件读写或导入外部 MCP。

---

## 仓库结构

| 目录 | 说明 |
|------|------|
| [`scholarmind-server/`](scholarmind-server/) | **FastAPI** 后端：JWT 鉴权、知识库 / 文献 / 条目 / 报告 API、PDF 解析任务、Chroma + Whoosh 索引、SSE 流式对话、MCP 工具 |
| [`scholarmind-web/`](scholarmind-web/) | **React + Vite + Tailwind** 前端：登录、知识库、文献与条目、对话、报告、工具、设置等页面 |
| [`docs/`](docs/) | 工程文档：PRD、开发流程、对话记忆方案、课题执行流程等 |
| [`assets/`](assets/) | README 界面截图（与根目录 README 同级引用） |

---

## 已实现能力（截至当前代码）

### 后端（`scholarmind-server`）

| 模块 | 能力 |
|------|------|
| **鉴权** | 邮箱注册 / 登录，JWT 访问令牌 |
| **知识库** | 创建、列表、重命名、删除（多租户按 `user_id` 隔离） |
| **文献** | PDF 上传、列表、预览、删除、失败重试；本地存储抽象 |
| **解析流水线** | PDF 文本抽取 → 切块 → Embedding（`bge` / `http` / `hash`）→ Chroma + Whoosh |
| **知识条目** | 对话提炼、URL 采集、草稿 / 发布 / 归档生命周期 |
| **对话** | `POST /api/v1/chat/stream`，SSE 推送 `trace_id`、`thinking_delta`、`delta`、`done`；注入 RAG 检索摘录 |
| **报告** | 由对话生成结构化报告，列表 / 详情 / 导出 Markdown |
| **MCP** | 内置联网搜索、文件读写等工具配置与开关 |
| **任务执行** | Celery + Redis，或 `INGEST_BACKGROUND_THREAD=true` 本机后台模式 |

### 前端（`scholarmind-web`）

| 路由 | 页面 |
|------|------|
| `/login` | 登录 / 注册 |
| `/chat` | 对话与研究（会话列表、知识库切换、流式 Markdown） |
| `/knowledge-bases` | 知识库管理 |
| `/documents` | 文献视图 + 条目视图 |
| `/documents/items/:kbId/:itemId` | 条目详情与编辑 |
| `/reports`、`/reports/:id` | 报告列表与详情 |
| `/evaluation` | RAG 评估看板（示意数据） |
| `/tools` | MCP 工具与集成 |
| `/settings` | 账户与偏好设置 |

对话正文使用 **[Streamdown](https://streamdown.ai/)** + Shiki 代码高亮与 CJK 排版优化。

### 规划中 / 占位

- LangGraph 深度 Agent 编排与执行过程 SSE 面板
- RAGAS 评估流水线对接真实看板数据
- 文献 PDF 页级引用跳转、Milvus 生产集群、Rerank
- Google OAuth、对象存储生产切换

---

## 快速开始

### 1. 准备环境

- **MySQL 8.x**：创建数据库与用户
- **Redis**（使用 Celery Worker 时）：默认 `redis://127.0.0.1:6379/0`
- **EdgeFN（或兼容 OpenAI 的网关）**：对话与（可选）云端 Embeddings

### 2. 后端

```bash
cd scholarmind-server
cp env.example .env
# 编辑 .env：DATABASE_URL、JWT_SECRET、EDGEFN_API_KEY 等

uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API 文档：<http://127.0.0.1:8000/docs>
- **不跑 Celery** 时：`.env` 设置 `INGEST_BACKGROUND_THREAD=true`
- **跑 Celery** 时：另开终端执行 `uv run celery -A app.workers.celery_app worker -l info`，且 Worker 与 API 共用同一 `.env`

### 3. 前端

```bash
cd scholarmind-web
pnpm install   # 或 npm install
pnpm dev       # 默认 http://localhost:5173
```

开发环境通过 `vite.config.ts` 将 `/api` 代理到 `http://127.0.0.1:8000`。

### 4. 首次使用

1. 打开 <http://localhost:5173/login> 注册并登录
2. 在「知识库」创建库，进入「文献管理」上传 PDF
3. 等待解析完成后，在「对话与研究」选择该库开始提问

---

## 主要环境变量（后端）

完整说明见 [`scholarmind-server/env.example`](scholarmind-server/env.example)。

| 变量 | 作用 |
|------|------|
| `DATABASE_URL` | MySQL 异步连接（`mysql+asyncmy://...`） |
| `JWT_SECRET` | JWT 签发密钥 |
| `STORAGE_LOCAL_ROOT` | 上传文件本地根路径 |
| `CHROMA_DATA_PATH` / `WHOOSH_INDEX_ROOT` | 向量与全文索引目录 |
| `EDGEFN_API_KEY` / `EDGEFN_API_BASE_URL` / `EDGEFN_CHAT_MODEL` | 对话模型网关 |
| `EMBEDDING_MODE` | `bge` \| `http` \| `hash` |
| `INGEST_BACKGROUND_THREAD` | `true` 时在本进程内异步解析（开发友好） |
| `REDIS_URL` / `CELERY_TASK_ALWAYS_EAGER` | Celery 任务队列 |

**切勿**将真实 `.env` 或密钥提交到版本库。

---

## 测试与质量

```bash
cd scholarmind-server
uv sync --dev
uv run pytest tests/ -q
```

```bash
cd scholarmind-web
pnpm run build
```

---

## 相关文档

- [ScholarMind PRD v2.0](docs/ScholarMind_PRD_v2.0.md) — 产品需求规格
- [ScholarMind 开发流程与步骤 v1.2](docs/ScholarMind_开发流程与步骤_v1.md) — 模块与里程碑映射
- [对话记忆与上下文技术方案](docs/ScholarMind_对话记忆与上下文技术方案_v1.md)
- [课题最高规格执行流程](docs/ScholarMind_课题最高规格执行流程_v1.md)
- [scholarmind-server README](scholarmind-server/README.md)

---

## 许可证与贡献

许可证以各子包声明为准。贡献前请阅读 PRD 与 `docs/` 下的流程文档，保持 **纵向切片** 与里程碑对齐。
