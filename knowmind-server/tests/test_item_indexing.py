from app.services.item_indexing import normalize_index_text


def test_normalize_index_text_strips_code_fence_and_prefixes_title() -> None:
    raw = "```html\n<div>姓名：杜昱微</div>\n```"
    out = normalize_index_text("杜昱微的个人信息", raw)
    assert "杜昱微的个人信息" in out
    assert "```" not in out
    assert "杜昱微" in out
