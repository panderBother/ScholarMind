from app.utils.db_text import clamp_mediumtext


def test_clamp_mediumtext_keeps_short_text() -> None:
    assert clamp_mediumtext("hello") == "hello"


def test_clamp_mediumtext_truncates_by_bytes() -> None:
    text = "中" * 100_000
    out = clamp_mediumtext(text, max_bytes=1000)
    assert out is not None
    assert len(out.encode("utf-8")) <= 1000
