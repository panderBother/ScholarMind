from app.ingest.chunking import semantic_chunk_text, _pack_units


def test_semantic_chunk_short_text_single_piece() -> None:
    chunks = semantic_chunk_text("你好，世界。")
    assert len(chunks) == 1
    assert "你好" in chunks[0].text


def test_semantic_chunk_respects_max_chars() -> None:
    para = "这是测试句子。" * 80
    body = "\n\n".join([f"段落{i}：{para}" for i in range(4)])
    chunks = semantic_chunk_text(body, max_chars=640, min_chars=120)
    assert len(chunks) >= 2
    for ch in chunks:
        assert len(ch.text) <= 640


def test_pack_units_merges_short_fragments() -> None:
    units = ["短。", "也短。", "第三段稍长一些的内容用于测试合并逻辑。" * 3]
    chunks = _pack_units(units, min_chars=120, max_chars=640, page=0, overlap=100)
    assert chunks
    for ch in chunks:
        assert len(ch.text) <= 640


def test_pack_units_does_not_merge_to_fill_max() -> None:
    units = ["a" * 200, "b" * 200]
    chunks = _pack_units(units, min_chars=120, max_chars=640, page=0, overlap=100)
    assert len(chunks) == 2
    assert len(chunks[0].text) == 200
    assert len(chunks[1].text) == 200
