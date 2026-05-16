from app.services.chat_file_tools import (
    build_read_calls,
    build_write_calls,
    expand_path_candidates,
    has_read_intent,
    infer_write_from_user_message,
    parse_prompt_tool_calls,
)


def test_expand_path_e_disk_chinese() -> None:
    user = "帮我将E盘里的velochat项目聊天.md文件里面的东西给我总结一下"
    paths = expand_path_candidates([user])
    assert any("velochat" in p.lower() for p in paths)
    assert any(p.upper().startswith("E:") for p in paths)
    assert has_read_intent(user)
    assert len(build_read_calls([user])) >= 1


def test_build_write_from_user_and_assistant() -> None:
    user = "请保存到 D:\\notes\\report.md"
    assistant = "# 报告标题\n\n这是正文内容，足够长以便写入文件。"
    calls = build_write_calls([user], assistant)
    assert len(calls) == 1


def test_parse_tool_block() -> None:
    text = '<scholarmind_tool_call>{"name": "read_document", "arguments": {"path": "E:\\\\a.md"}}</scholarmind_tool_call>'
    calls = parse_prompt_tool_calls(text)
    assert calls and calls[0][0] == "read_document"


def test_infer_write_from_user_message() -> None:
    user = "请保存到 D:\\notes\\out.md\n\n# Title\n\nbody"
    got = infer_write_from_user_message(user)
    assert got is not None
