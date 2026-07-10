"""会话状态管理：本地 JSON 持久化，跨进程/重启不丢。

简化后的模型：一个会话 = 一个聊天对话历史 + 一个独立字幕暂存区。

- messages：发给 LLM 的对话历史，永远累积（整场面试一个对话）。
- subtitle_lines：语音识别出的字幕，用户确认后整体发出去，
  发送时打包成一条 user message 追加进 messages，然后清空。
两者独立：删字幕/清字幕不影响对话历史。

持久化：SessionStore 落盘到本地 JSON（生产用）；path=None 时纯内存（测试用）。
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from typing import Dict, List

from app.schemas import Message

TITLE_MAX_LEN = 24  # 会话标题取首句的前 24 字

DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "sessions.json",
)


class InterviewSession:
    """一场面试的一个会话。"""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        # 发给 LLM 的对话历史（role/content）。整场面试累积，不自动清。
        self.messages: List[Message] = []
        # 字幕暂存区：语音识别的定稿句子。发送给 LLM 时整体打包，然后清空。
        self.subtitle_lines: List[str] = []
        # 会话标题：首条 user 消息时自动设为前 N 字。None 时前端显示"新对话"。
        self.title: str | None = None
        # 最后更新时间（unix 秒），用于会话列表排序。
        self.updated_at: float = time.time()

    @property
    def subtitle_text(self) -> str:
        """字幕区的完整文本（换行拼接）。只读。"""
        return "\n".join(self.subtitle_lines)

    def touch(self) -> None:
        """更新最后修改时间。"""
        self.updated_at = time.time()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": [{"role": m.role, "content": m.content} for m in self.messages],
            "subtitle_lines": list(self.subtitle_lines),
            "title": self.title,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "InterviewSession":
        s = cls(session_id=d["session_id"])
        s.messages = [Message(role=m["role"], content=m["content"]) for m in d.get("messages", [])]
        s.subtitle_lines = list(d.get("subtitle_lines", []))
        s.title = d.get("title")
        s.updated_at = d.get("updated_at", s.updated_at)
        return s

    # ---- 对话历史 ----
    def add_message(self, role: str, content: str) -> None:
        """追加一条对话消息到历史。空文本忽略。首条 user 消息自动设标题。"""
        content = content.strip()
        if not content:
            return
        self.messages.append(Message(role=role, content=content))
        # 首条 user 消息自动生成标题
        if role == "user" and self.title is None:
            self.title = content[:TITLE_MAX_LEN]
        self.touch()

    def clear_messages(self) -> None:
        """清空整个对话历史（重置）。标题保留，更新时间。"""
        self.messages = []
        self.touch()

    def rename(self, title: str) -> None:
        """手动重命名会话。"""
        self.title = title.strip() or None
        self.touch()

    # ---- 字幕区 ----
    def add_subtitle(self, text: str) -> None:
        """追加一句语音定稿字幕。空文本忽略。"""
        text = text.strip()
        if not text:
            return
        self.subtitle_lines.append(text)

    def remove_subtitle_line(self, index: int) -> bool:
        """删除字幕区第 index 行（0 基）。越界返回 False。"""
        if 0 <= index < len(self.subtitle_lines):
            del self.subtitle_lines[index]
            return True
        return False

    def clear_subtitles(self) -> None:
        """清空字幕区（不影响对话历史）。"""
        self.subtitle_lines = []

    def consume_subtitles(self) -> str:
        """把字幕区全部内容打包返回，并清空字幕区。空时返回空串。"""
        text = self.subtitle_text
        self.subtitle_lines = []
        return text


class SessionStore:
    """按 session_id 索引的会话存储。

    path 传入时落盘到本地 JSON（生产用）；path=None 时纯内存（测试用）。
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = path
        self._sessions: Dict[str, InterviewSession] = {}
        self._lock = threading.Lock()
        if path is not None:
            self._load()

    # ---- 持久化 ----
    def _load(self) -> None:
        """启动时从磁盘加载已有会话。文件不存在或损坏时视为空。"""
        assert self._path is not None
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for s in data.get("sessions", []):
                session = InterviewSession.from_dict(s)
                self._sessions[session.session_id] = session
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, KeyError):
            # 文件损坏：视为空，避免启动崩溃
            pass

    def _save(self) -> None:
        """原子写：先写 .tmp 再 rename。path=None 时跳过。"""
        if self._path is None:
            return
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        data = {"sessions": [s.to_dict() for s in self._sessions.values()]}
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)

    # ---- 业务 ----
    def create(self) -> InterviewSession:
        sid = uuid.uuid4().hex
        s = InterviewSession(sid)
        with self._lock:
            self._sessions[sid] = s
            self._save()
        return s

    def get(self, session_id: str) -> InterviewSession | None:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> InterviewSession:
        existing = self._sessions.get(session_id)
        if existing is not None:
            return existing
        return self.create()

    def list_summaries(self) -> List[dict]:
        """返回所有会话的摘要（id/title/updated_at），按更新时间倒序。列表不含完整消息。"""
        items = [
            {
                "session_id": s.session_id,
                "title": s.title or "新对话",
                "updated_at": s.updated_at,
            }
            for s in self._sessions.values()
        ]
        items.sort(key=lambda x: x["updated_at"], reverse=True)
        return items

    def delete(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._save()
                return True
            return False

    def save(self, session_id: str) -> None:
        """显式持久化某个会话（add_message 等修改后由调用方触发）。"""
        with self._lock:
            if session_id in self._sessions:
                self._save()
