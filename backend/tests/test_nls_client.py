"""测试 NLS ASR 会话的消息分发逻辑（纯 JSON 解析，不依赖真实 SDK）。"""

from unittest.mock import MagicMock

from app.services.nls_client import NlsAsrSession


def _make_session():
    cb = MagicMock()
    session = NlsAsrSession(
        on_partial=cb.on_partial,
        on_final=cb.on_final,
        app_key="ak",
        token="T",
    )
    return session, cb


def test_on_sentence_begin_calls_partial_with_empty():
    session, cb = _make_session()
    msg = (
        '{"header":{"name":"SentenceBegin","status":20000000},'
        '"payload":{"index":0}}'
    )
    session._handle_message(msg)
    cb.on_partial.assert_called_once_with("")
    cb.on_final.assert_not_called()


def test_on_transcription_result_changed_calls_partial_with_text():
    session, cb = _make_session()
    msg = (
        '{"header":{"name":"TranscriptionResultChanged","status":20000000},'
        '"payload":{"result":"你好"}}'
    )
    session._handle_message(msg)
    cb.on_partial.assert_called_with("你好")
    cb.on_final.assert_not_called()


def test_on_sentence_end_calls_final_with_text():
    session, cb = _make_session()
    msg = (
        '{"header":{"name":"SentenceEnd","status":20000000},'
        '"payload":{"result":"你好世界"}}'
    )
    session._handle_message(msg)
    cb.on_final.assert_called_once_with("你好世界")
    cb.on_partial.assert_not_called()


def test_unknown_event_is_ignored():
    session, cb = _make_session()
    msg = '{"header":{"name":"TaskFailed","status":40000000},"payload":{}}'
    session._handle_message(msg)  # 不应抛异常
    cb.on_partial.assert_not_called()
    cb.on_final.assert_not_called()


def test_task_failed_notifies_on_error():
    """TaskFailed 是 NLS 服务端明确送达的失败（SDK on_error 不可靠），应通知前端。"""
    cb = MagicMock()
    session = NlsAsrSession(
        on_partial=cb.on_partial,
        on_final=cb.on_final,
        app_key="ak",
        token="T",
        on_error=cb.on_error,
    )
    msg = (
        '{"header":{"name":"TaskFailed","status":40000000,'
        '"status_text":"Gateway:TOO_MANY_REQUESTS:Too many requests!"},"payload":{}}'
    )
    session._handle_message(msg)
    cb.on_error.assert_called_once()
    assert "TOO_MANY_REQUESTS" in cb.on_error.call_args[0][0]
    cb.on_final.assert_not_called()


def test_task_failed_without_status_text_uses_default():
    """无 status_text 时 on_error 用默认文案，不抛异常。"""
    cb = MagicMock()
    session = NlsAsrSession(
        on_partial=cb.on_partial,
        on_final=cb.on_final,
        app_key="ak",
        token="T",
        on_error=cb.on_error,
    )
    session._handle_message('{"header":{"name":"TaskFailed","status":40000000},"payload":{}}')
    cb.on_error.assert_called_once()
    assert "未知错误" in cb.on_error.call_args[0][0]


def test_missing_payload_does_not_crash():
    session, cb = _make_session()
    msg = '{"header":{"name":"TranscriptionResultChanged","status":20000000}}'
    session._handle_message(msg)
    cb.on_partial.assert_called_with("")
