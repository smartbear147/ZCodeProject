"""测试 ChatService（单对话历史 + 文档注入）。"""

from unittest.mock import MagicMock

import pytest

from app.prompts import BASE_SYSTEM_PROMPT
from app.services.chat_service import ChatService
from app.services.session import SessionStore


def _fake_llm(stream_chunks):
    llm = MagicMock()
    llm.stream.return_value = iter(stream_chunks)
    return llm


def test_build_messages_system_plus_history():
    store = SessionStore()
    s = store.create()
    s.add_message("user", "问题1")
    s.add_message("assistant", "回答1")
    svc = ChatService(llm=_fake_llm([]), store=store)

    msgs = svc.build_messages(s)

    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == BASE_SYSTEM_PROMPT
    assert msgs[1] == {"role": "user", "content": "问题1"}
    assert msgs[2] == {"role": "assistant", "content": "回答1"}


def test_chat_stream_appends_user_and_assistant():
    store = SessionStore()
    s = store.create()
    svc = ChatService(llm=_fake_llm(["回", "答"]), store=store)

    chunks = list(svc.chat_stream(s.session_id, "问题"))

    assert "".join(chunks) == "回答"
    assert len(s.messages) == 2
    assert s.messages[0].role == "user"
    assert s.messages[0].content == "问题"
    assert s.messages[1].role == "assistant"
    assert s.messages[1].content == "回答"


def test_chat_stream_unknown_session_raises():
    store = SessionStore()
    svc = ChatService(llm=_fake_llm([]), store=store)
    with pytest.raises(KeyError):
        list(svc.chat_stream("nonexistent", "问题"))


def test_build_messages_includes_resume_from_doc_store():
    from app.services.document_store import DocumentStore

    docs = DocumentStore()
    docs.add(filename="r.pdf", doc_type="resume", text="我在腾讯做过后端", size_bytes=10)
    store = SessionStore()
    s = store.create()
    svc = ChatService(llm=_fake_llm([]), store=store, doc_store=docs)

    msgs = svc.build_messages(s)

    assert "我在腾讯做过后端" in msgs[0]["content"]


def test_chat_stream_accumulates_history_across_calls():
    """多次对话，历史持续累积。"""
    store = SessionStore()
    s = store.create()
    llm = MagicMock()
    llm.stream.side_effect = [iter(["答1"]), iter(["答2"])]
    svc = ChatService(llm=llm, store=store)

    list(svc.chat_stream(s.session_id, "问1"))
    list(svc.chat_stream(s.session_id, "问2"))

    # 4 条历史：user,assistant,user,assistant
    assert len(s.messages) == 4
    # 第二次调用时 LLM 收到的 messages 应包含第一次的问答
    second_call_msgs = llm.stream.call_args_list[1].args[0]
    assert any(m["content"] == "问1" for m in second_call_msgs)
    assert any(m["content"] == "答1" for m in second_call_msgs)
