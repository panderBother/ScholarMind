from app.services.distill_service import draft_limit_for_gap
from app.utils.llm_json import parse_llm_json_array


def test_parse_llm_json_array_with_markdown_brackets() -> None:
    raw = """```json
[{"title": "测试", "content": "见引用 [1] 与 [2] 说明", "tags": ["a"]}]
```
说明：以上即为草稿。"""
    out = parse_llm_json_array(raw)
    assert out is not None
    assert len(out) == 1
    assert out[0]["title"] == "测试"


def test_parse_llm_json_array_stops_before_trailing_text() -> None:
    raw = '[{"title":"A","content":"body","tags":[]}]\n\n以上是 JSON。'
    out = parse_llm_json_array(raw)
    assert out is not None
    assert out[0]["title"] == "A"


def test_draft_limit_for_gap_scales_with_evidence() -> None:
    from app.models.orm import KnowledgeGap

    gap = KnowledgeGap(
        id="g1",
        kb_id="kb",
        user_id="u",
        gap_key="k",
        trigger_rule="high_miss",
        sample_queries=["说一下IT专业英语课程考核方案的评分标准"],
        hit_count=2,
        status="open",
    )
    assert draft_limit_for_gap(gap) == 1

    gap2 = KnowledgeGap(
        id="g2",
        kb_id="kb",
        user_id="u",
        gap_key="k2",
        trigger_rule="high_miss",
        sample_queries=["问题 A", "问题 B"],
        hit_count=4,
        status="open",
    )
    assert draft_limit_for_gap(gap2) == 2
