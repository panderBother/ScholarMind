from __future__ import annotations

import logging

from app.services.chat_memory_worker import process_chat_memory_after_turn
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="scholarmind.chat_memory.after_turn")
def process_chat_memory_after_turn_task(
    *,
    conversation_id: str,
    user_id: str,
    user_text: str,
    assistant_text: str,
    assistant_message_id: str,
) -> None:
    process_chat_memory_after_turn(
        conversation_id=conversation_id,
        user_id=user_id,
        user_text=user_text,
        assistant_text=assistant_text,
        assistant_message_id=assistant_message_id,
    )
    log.info("chat_memory after_turn done conv=%s", conversation_id)
