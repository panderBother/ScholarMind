from app.ingest.chunking import semantic_chunk_text


def test_semantic_chunk_short_text_single_piece() -> None:
    chunks = semantic_chunk_text("你好，世界。")
    assert len(chunks) == 1
    assert "你好" in chunks[0].text


def test_semantic_chunk_long_text_multiple_pieces() -> None:
    para = "这是测试句子。" * 80
    body = "\n\n".join([f"段落{i}：{para}" for i in range(4)])
    chunks = semantic_chunk_text(body, max_chars=800)
    assert len(chunks) >= 2
    for ch in chunks:
        assert len(ch.text) <= 900
