"""对话业务：组装 prompt（含简历/题库），追加消息，流式生成。

简化后的模型：一个会话 = 一个不断累积的对话历史。
- chat_stream：把 user 消息追加进历史，流式生成 assistant 回复，追加进历史。
- 字幕发送场景：路由层先把字幕打包成 user 消息内容，再调 chat_stream。
"""

from typing import Iterator, List

from app.prompts import build_system_prompt
from app.services.document_store import DocumentStore
from app.services.llm import LlmClient
from app.services.session import InterviewSession, SessionStore


class ChatService:
    def __init__(
        self,
        llm: LlmClient,
        store: SessionStore,
        doc_store: DocumentStore | None = None,
    ) -> None:
        self._llm = llm
        self._store = store
        self._doc_store = doc_store

    def build_messages(self, session: InterviewSession) -> List[dict]:
        """组装发给 LLM 的 messages：system(含文档) + 对话历史。"""
        system_prompt = self._build_system_prompt_with_docs()
        messages: List[dict] = [{"role": "system", "content": system_prompt}]
        for msg in session.messages:
            messages.append({"role": msg.role, "content": msg.content})
        return messages

    def _build_system_prompt_with_docs(self) -> str:
        """从 doc_store 取简历/题库全文，拼进 system prompt。无 doc_store 时用基础 prompt。"""
        if self._doc_store is None:
            return build_system_prompt(resume_text="", qa_text="")
        resume_text = "\n\n".join(d.text for d in self._doc_store.get_by_type("resume"))
        qa_text = "\n\n".join(d.text for d in self._doc_store.get_by_type("qa"))
        return build_system_prompt(resume_text=resume_text, qa_text=qa_text)

    def chat_stream(self, session_id: str, user_content: str) -> Iterator[str]:
        """追加 user 消息，流式生成 assistant 回复，追加进历史。

        Args:
            user_content: 这一条 user 消息的内容（已由路由层决定，字幕或手打）。

        Yields:
            assistant 回复的 token 片段。
        """
        session = self._store.get(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        # 追加 user 消息
        session.add_message("user", user_content)
        self._store.save(session_id)
        # 流式生成
        messages = self.build_messages(session)
        acc: list[str] = []
        for delta in self._llm.stream(messages):
            acc.append(delta)
            yield delta
        # 追加完整 assistant 回复进历史并落盘
        session.add_message("assistant", "".join(acc))
        self._store.save(session_id)
