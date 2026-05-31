from pydantic import ValidationError

from app.models.schemas import ChatRequest


def test_chat_request_allows_attachments_only() -> None:
    req = ChatRequest(message="", attachment_ids=["abc-123"])
    assert req.attachment_ids == ["abc-123"]


def test_chat_request_requires_message_or_attachment() -> None:
    try:
        ChatRequest(message="", attachment_ids=[])
        assert False, "expected validation error"
    except ValidationError:
        pass
