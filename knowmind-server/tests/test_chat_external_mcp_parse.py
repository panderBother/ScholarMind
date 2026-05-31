import json

from app.services.chat_external_mcp_parse import parse_text_tool_calls, strip_text_tool_calls


def test_parse_kimi_style_tool_call_block() -> None:
    text = """
分析完毕，准备调用文生图工具。

<|tool_calls_begin|> <|tool_call_begin|> function <|tool_sep|> 5e86dab7-bf8d-43da-8198-5fc9a2cee27f::generate_image
```json
{
  "17:BizyAir_GPT_IMAGE_2_T2I_API.prompt": "一只可爱的猫咪端坐在斑驳的阳光下",
  "17:BizyAir_GPT_IMAGE_2_T2I_API.aspect_ratio": "1:1"
}
``` <|tool_call_end|> <|tool_calls_end|>
"""
    known = {"5e86dab7-bf8d-43da-8198-5fc9a2cee27f::generate_image"}
    calls = parse_text_tool_calls(text, known_names=known)
    assert len(calls) == 1
    name, args = calls[0]
    assert name == "5e86dab7-bf8d-43da-8198-5fc9a2cee27f::generate_image"
    obj = json.loads(args)
    assert "17:BizyAir_GPT_IMAGE_2_T2I_API.prompt" in obj


def test_parse_tool_call_with_spaced_tokens() -> None:
    text = """
< | tool_calls_begin | > < | tool_call_begin | > function < | tool_sep | > abc-123::search
```json
{"q": "cat"}
```
< | tool_call_end | > < | tool_calls_end | >
"""
    calls = parse_text_tool_calls(text, known_names={"abc-123::search"})
    assert len(calls) == 1
    assert calls[0][0] == "abc-123::search"


def test_strip_text_tool_calls() -> None:
    text = "前置说明\n<|tool_calls_begin|> <|tool_call_begin|> function <|tool_sep|> x::t\n```json\n{}\n```\n<|tool_call_end|>\n<|tool_calls_end|>\n后置说明"
    cleaned = strip_text_tool_calls(text)
    assert "tool_sep" not in cleaned
    assert "前置说明" in cleaned
    assert "后置说明" in cleaned
