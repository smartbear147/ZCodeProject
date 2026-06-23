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


def test_missing_payload_does_not_crash():
    session, cb = _make_session()
    msg = '{"header":{"name":"TranscriptionResultChanged","status":20000000}}'
    session._handle_message(msg)
    cb.on_partial.assert_called_with("")
