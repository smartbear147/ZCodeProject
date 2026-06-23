"""会话状态管理（内存）。本期单进程、不持久化。"""

from __future__ import annotations

import uuid
from typing import Dict, List

from app.schemas import Turn


class InterviewSession:
    """一场面试的一个会话。"""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.current_turn_text: str = ""
        self.history_turns: List[Turn] = []

    def append_final(self, text: str) -> None:
        """追加一句定稿字幕到当前轮次。空文本忽略。"""
        text = text.strip()
        if not text:
            return
        if self.current_turn_text:
            self.current_turn_text += "\n" + text
        else:
            self.current_turn_text = text

    def finalize_turn(self, suggestion: str) -> None:
        """把当前轮次结转为历史，记录建议，清空当前轮次。"""
        self.history_turns.append(
            Turn(question=self.current_turn_text, suggestion=suggestion)
        )
        self.current_turn_text = ""

    def clear_history(self) -> None:
        """清空历史轮次，但保留当前正在进行的轮次。"""
        self.history_turns = []


class SessionStore:
    """按 session_id 索引的会话存储（内存字典）。"""

    def __init__(self) -> None:
        self._sessions: Dict[str, InterviewSession] = {}

    def create(self) -> InterviewSession:
        sid = uuid.uuid4().hex
        s = InterviewSession(sid)
        self._sessions[sid] = s
        return s

    def get(self, session_id: str) -> InterviewSession | None:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> InterviewSession:
        existing = self._sessions.get(session_id)
        if existing is not None:
            return existing
        return self.create()

    def clear_history(self, session_id: str) -> None:
        s = self.get(session_id)
        if s is not None:
            s.clear_history()
