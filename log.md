# KnowMind 变更日志

## 2026-05-25 16:30 - 请求追踪 RAG 命中数修复
- 修改人：AI助手
- 影响文件：
  - knowmind-server/app/services/chat_service.py （修改）
- 变更概要：
  - 修复 RAG 检索完成后 `rag_hits` 列表引用未同步，导致追踪栏误报「未命中」
  - 兜底：若上下文已含摘录标题则按摘录数统计命中
- 关联需求：请求追踪 RAG 准确性

## 2026-05-25 16:00 - 请求追踪栏精简
- 修改人：AI助手
- 影响文件：
  - knowmind-web/src/components/RequestTracePanel.tsx （修改）
  - knowmind-web/src/pages/ChatPage.tsx （修改）
  - knowmind-server/app/services/chat_service.py （修改）
- 变更概要：
  - 移除追踪栏中的「推理过程」重复条目（推理正文仅在主区「思维链」展示）
  - 过滤 request / prompt_assembly / complete / skipped 等冗余步骤
  - 修复同一步骤 running 状态重复追加的问题；RAG 步骤展示平均相关度
- 关联需求：请求追踪准确性

## 2026-05-25 15:10 - 对话 Markdown 预览修复
- 修改人：AI助手
- 影响文件：
  - knowmind-web/src/utils/prepareAssistantMarkdown.ts （新增）
  - knowmind-web/src/components/AssistantMarkdown.tsx （修改）
  - knowmind-web/src/index.css （修改）
- 变更概要：
  - 剥掉模型输出的外层 ```markdown 围栏（含嵌套 mermaid 等内层代码块场景），避免整段被当成源码高亮
  - 为对话区 `.streamdown-chat-root` 补齐标题/列表/链接等排版样式
- 关联需求：对话 Markdown 预览

## 2026-05-25 14:00 - 对话请求追踪动态化
- 修改人：AI助手
- 影响文件：
  - knowmind-server/app/services/chat_service.py （修改）
  - knowmind-web/src/services/chat.ts （修改）
  - knowmind-web/src/components/RequestTracePanel.tsx （新增）
  - knowmind-web/src/pages/ChatPage.tsx （修改）
  - README.md （修改）
- 变更概要：
  - 后端 SSE 新增 `agent_step` 事件，推送 RAG 检索、联网搜索、记忆召回、模型生成等步骤
  - 前端右侧「请求追踪」栏接入 SSE 实时渲染步骤时间线，替代静态占位文案
- 关联需求：对话页请求追踪
