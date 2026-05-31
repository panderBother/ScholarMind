from app.services.mcp_tool_args import coerce_arguments_for_schema


def test_coerce_16_9_to_allowed_aspect() -> None:
    schema = {
        "properties": {
            "17:BizyAir_GPT_IMAGE_1_T2I_API.size": {
                "type": "string",
                "enum": ["1:1", "2:3", "3:2"],
            },
        },
    }
    args = {"17:BizyAir_GPT_IMAGE_1_T2I_API.size": "16:9"}
    fixed, notes = coerce_arguments_for_schema(args, schema)
    assert fixed["17:BizyAir_GPT_IMAGE_1_T2I_API.size"] == "3:2"
    assert notes
