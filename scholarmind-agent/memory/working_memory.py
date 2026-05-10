from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class WorkingMemory:
    """
    会话工作记忆：存放高价值中间结论，避免上下文窗口被原始检索块占满。
    """

    session_id: str
    facts: list[str] = field(default_factory=list)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_fact(self, fact: str) -> None:
        self.facts.append(fact)
        self.updated_at = datetime.now(timezone.utc)
