"""测试音频/字幕 WebSocket 路由。

用 fake 替换 NlsAsrSession，避免真实 SDK 依赖。
fake 的 start() 会同步触发一次 final 回调，验证：
- session 被创建
- final 消息推回前端
- 定稿文本累积到 session
"""

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.deps import get_session_store, get_token_provider
from app.main import app
from app.services.session import SessionStore


def _override_deps() -> SessionStore:
    """注入空的内存 store 和假 token provider。"""
    store = SessionStore()
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_token_provider] = lambda: _DummyTokenProvider()
    return store


class _DummyTokenProvider:
    def get_token(self) -> str:
        return "FAKE_TOKEN"


class _FakeNls:
    """假 NLS：start 时记录回调并同步触发一次 final。"""

    last_instance = None

    def __init__(self, on_partial, on_final, app_key, token, **_):
        self.on_partial = on_partial
        self.on_final = on_final
        _FakeNls.last_instance = self

    def start(self, **_):
        # 同步触发一次 final（真实 SDK 在线程里异步触发，这里简化测试）
        self.on_final("你好面试官")

    def send_audio(self, _):
        pass

    def stop(self):
        pass


def test_audio_ws_creates_session_and_streams_final():
    store = _override_deps()
    _FakeNls.last_instance = None

    client = TestClient(app)

    with patch("app.routes.audio.NlsAsrSession", _FakeNls):
        with client.websocket_connect("/ws/audio") as ws:
            # 先发 start 文本帧
            ws.send_text(json.dumps({"type": "start"}))
            # 收到 ready
            ready = json.loads(ws.receive_text())
            assert ready["type"] == "ready"
            sid = ready["session_id"]
            # 收到 final（FakeNls.start 已同步触发）
            final_msg = json.loads(ws.receive_text())
            assert final_msg["type"] == "final"
            assert final_msg["text"] == "你好面试官"
            assert final_msg["session_id"] == sid
            # final 应已累积到 session 的字幕区
            assert store.get(sid).subtitle_text == "你好面试官"

    app.dependency_overrides.clear()


def test_audio_ws_without_start_ignores_audio():
    _override_deps()
    client = TestClient(app)

    with patch("app.routes.audio.NlsAsrSession", _FakeNls):
        with client.websocket_connect("/ws/audio") as ws:
            # 直接发音频帧（未 start），不应报错
            ws.send_bytes(b"\x00" * 8)

    app.dependency_overrides.clear()
