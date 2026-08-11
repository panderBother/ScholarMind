from contextlib import contextmanager

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.orm import Conversation, ConversationFact
from app.services.chat_memory_worker import update_working_memory_sync
from app.services.edgefn_client import build_chat_messages_multi


def test_working_memory_is_injected_into_prompt() -> None:
    messages = build_chat_messages_multi(
        deep_research=False,
        web_search=False,
        kb_context=None,
        memory_summaries="",
        working_memory="- preferred_language: Python",
        memory_retrieval="",
        history_pairs=[("user", "继续")],
    )
    assert "会话工作记忆" in messages[0]["content"]
    assert "preferred_language: Python" in messages[0]["content"]


def test_working_memory_extraction_upserts_fact(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        session.add(Conversation(id="conv1", user_id="user1"))
        session.commit()

    @contextmanager
    def test_scope():
        session = factory()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    async def fake_complete(_messages):
        return (
            "",
            '[{"key":"preferred_language","value":"Python","action":"upsert","confidence":0.95}]',
            {},
        )

    monkeypatch.setenv("EDGEFN_API_KEY", "test-key")
    get_settings.cache_clear()
    monkeypatch.setattr("app.services.chat_memory_worker.session_scope", test_scope)
    monkeypatch.setattr("app.services.chat_memory_worker.complete_chat", fake_complete)

    update_working_memory_sync(
        conversation_id="conv1",
        user_id="user1",
        user_text="后续代码都用 Python",
        assistant_text="好的",
        assistant_message_id="msg1",
    )

    with factory() as session:
        fact = session.scalar(select(ConversationFact))
        assert fact is not None
        assert fact.fact_key == "preferred_language"
        assert fact.fact_value == "Python"
        assert fact.confidence == 0.95

    get_settings.cache_clear()
