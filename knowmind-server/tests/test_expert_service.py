from app.services.expert_service import build_system_prompt_from_items


class _Item:
    def __init__(self, title: str, content: str = "", summary: str | None = None, tags=None):
        self.title = title
        self.content = content
        self.summary = summary
        self.tags = tags


def test_build_system_prompt_includes_items() -> None:
    items = [_Item("Alpha", content="body alpha"), _Item("Beta", summary="sum beta")]
    prompt = build_system_prompt_from_items("测试库", items)
    assert "测试库" in prompt
    assert "Alpha" in prompt
    assert "Beta" in prompt
    assert "sum beta" in prompt


def test_build_system_prompt_empty_items() -> None:
    prompt = build_system_prompt_from_items("空库", [])
    assert "尚无已发布条目" in prompt
