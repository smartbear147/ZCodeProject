"""生成建议业务：组装 prompt，调 LLM，结转轮次。"""

from typing import List

from app.prompts import SYSTEM_PROMPT
from app.services.llm import LlmClient
from app.services.session import InterviewSession, SessionStore

CURRENT_TURN_PREFIX = "面试官问："


class SuggestService:
    def __init__(self, llm: LlmClient, store: SessionStore) -> None:
        self._llm = llm
        self._store = store

    def build_messages(self, session: InterviewSession) -> List[dict]:
        """组装 messages：system + 历史(多轮 user/assistant) + 当前 user。"""
        messages: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in session.history_turns:
            messages.append({"role": "user", "content": CURRENT_TURN_PREFIX + turn.question})
            messages.append({"role": "assistant", "content": turn.suggestion})
        messages.append(
            {"role": "user", "content": CURRENT_TURN_PREFIX + session.current_turn_text}
        )
        return messages

    def suggest(self, session_id: str) -> str:
        """生成建议并结转当前轮次。返回建议文本。"""
        session = self._store.get(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        messages = self.build_messages(session)
        suggestion = self._llm.generate(messages)
        session.finalize_turn(suggestion=suggestion)
        return suggestion
