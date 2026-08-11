"""生成确定性的中文 CrossEncoder 对照评测集。"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FACTS = [
    ("混合检索", "如何实现混合检索", "向量检索与 BM25 双路召回后，通过 RRF 对候选结果融合去重。"),
    ("RRF", "RRF 在检索链路中的作用是什么", "RRF 按各检索结果的倒数排名计算融合分数，降低不同分值尺度的影响。"),
    ("CrossEncoder", "为什么使用 CrossEncoder 精排", "CrossEncoder 联合编码查询与片段，对 RRF 候选进行二阶段相关性重排。"),
    ("精排降级", "精排服务异常时如何处理", "CrossEncoder 调用失败时自动保留 RRF 原始顺序，避免检索链路不可用。"),
    ("相关度阈值", "如何过滤低质量检索片段", "根据 CrossEncoder 相关度设置最低分阈值，过滤低相关候选片段。"),
    ("向量索引", "Chroma 在系统中负责什么", "Chroma 保存文档片段向量，并执行语义相似度检索。"),
    ("关键词索引", "Whoosh 在系统中负责什么", "Whoosh 建立 BM25 全文索引，召回包含关键术语的文档片段。"),
    ("异步入库", "文档如何异步写入知识库", "Knowledge Pipeline 异步执行解析、切分、向量化以及双索引写入。"),
    ("任务队列", "Celery 在文档处理中有什么作用", "Celery 通过 Redis 队列把耗时的文档解析任务交给独立 Worker 执行。"),
    ("后台线程", "开发环境为什么提供后台线程模式", "后台线程模式无需启动 Redis 和 Celery Worker，便于本地开发调试。"),
    ("状态机", "如何展示文档处理进度", "状态机维护 pending、processing、done、failed 状态并向前端展示进度。"),
    ("失败重试", "文档解析失败后如何恢复", "失败任务可重新投递队列，并从可恢复阶段继续执行。"),
    ("增量更新", "知识内容更新后如何维护索引", "只重新处理发生变化的内容，并增量更新向量索引和 BM25 索引。"),
    ("多租户", "知识库如何实现租户隔离", "通过 user_id 与 kb_id 约束元数据、文件和索引访问范围。"),
    ("视觉解析", "扫描文档如何提取内容", "对扫描 PDF 和图片调用视觉理解或 OCR，提取文本和版面信息。"),
    ("多格式解析", "平台支持哪些文档接入方式", "统一解析 PDF、Word、Excel、Markdown 和网页等多种来源。"),
    ("SSE", "如何实时展示 Agent 执行轨迹", "FastAPI 通过 SSE 事件流持续推送计划、工具调用和生成结果。"),
    ("执行计划", "复杂问题如何生成执行步骤", "Agent 根据查询和会话上下文动态生成多阶段执行计划。"),
    ("并发检索", "多个知识来源如何提高查询速度", "对向量、BM25 与工具数据源并发检索，并汇总候选结果。"),
    ("重试策略", "外部检索请求失败怎么办", "外部调用采用有限次数重试、超时控制和指数退避。"),
    ("工作记忆", "近期对话信息如何保留", "工作记忆保存最近轮次和高相关历史片段，供当前推理使用。"),
    ("对话摘要", "长对话超出上下文窗口怎么办", "周期生成对话摘要并压缩早期消息，控制上下文长度。"),
    ("MCP", "平台如何扩展外部工具", "通过 MCP 标准注册和调用外部工具，并统一处理工具输入与输出。"),
    ("可溯源回答", "如何让知识问答结果可核对", "回答携带命中文档、片段和页码引用，支持用户回查原文。"),
    ("缓存", "Redis 除任务队列外还有什么用途", "Redis 缓存会话热数据和临时执行状态，减少重复读取。"),
]

QUESTION_FORMS = [
    "{q}？", "请说明：{q}。", "系统中，{q}？", "KnowMind 里{q}？",
    "从工程实现看，{q}？", "请简述{q}。", "关于{name}，{q}？", "我想了解{name}：{q}？",
]

def main() -> None:
    rng = random.Random(20260808)
    rows = []
    for fact_index, (name, question, answer) in enumerate(FACTS):
        same_group = FACTS[max(0, fact_index - 3): fact_index] + FACTS[fact_index + 1: fact_index + 4]
        other = [f for f in FACTS if f[0] != name and f not in same_group]
        for form_index, form in enumerate(QUESTION_FORMS):
            negatives = list(same_group)
            rng.shuffle(negatives)
            negatives = negatives[:3] + rng.sample(other, 2)
            candidates = [{"id": f"n{fact_index}_{i}", "text": f[2], "relevant": False} for i, f in enumerate(negatives)]
            relevant = {"id": f"r{fact_index}", "text": answer, "relevant": True}
            # 模拟 RRF 并不完美的初始顺序，相关片段均匀分布在 1~6 位。
            candidates.insert((fact_index + form_index) % 6, relevant)
            rows.append({"question": form.format(q=question, name=name), "topic": name, "candidates": candidates})
    output = ROOT / "datasets" / "rerank_benchmark_200.jsonl"
    output.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    print(f"generated {len(rows)} samples: {output}")

if __name__ == "__main__":
    main()
