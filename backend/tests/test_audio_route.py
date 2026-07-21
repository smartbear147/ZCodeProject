"""测试音频/字幕 WebSocket 路由。

通过 override get_asr_factory 注入假 ASR（不依赖真实 SDK / 网络）。
fake 的 start() 会同步触发一次 final 回调，验证：
- session 被创建
- final 消息推回前端
- 定稿文本累积到 session
"""

import json

from fastapi.testclient import TestClient

from app.deps import get_asr_factory, get_session_store
from app.main import app
from app.services.session import SessionStore


class _FakeAsr:
    """假 ASR 会话：start 时记录回调并同步触发一次 final。"""

    last_instance = None

    def __init__(self, on_partial, on_final):
        self.on_partial = on_partial
        self.on_final = on_final
        self.stopped = False
        _FakeAsr.last_instance = self

    def start(self, **_):
        # 同步触发一次 final（真实 ASR 异步触发，这里简化测试）
        self.on_final("你好面试官")

    def send_pcm(self, _):
        pass

    def stop(self):
        self.stopped = True


def _fake_asr_factory(on_partial, on_final, loop, on_error=None):
    """构造假 ASR 会话的工厂（签名与 deps.get_asr_factory 返回的 make 一致）。"""
    return _FakeAsr(on_partial, on_final)


def _override_deps() -> SessionStore:
    """注入空的内存 store 和假 ASR 工厂。"""
    store = SessionStore()
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_asr_factory] = lambda: _fake_asr_factory
    return store


def test_audio_ws_creates_session_and_streams_final():
    store = _override_deps()
    _FakeAsr.last_instance = None

    client = TestClient(app)

    with client.websocket_connect("/ws/audio") as ws:
        # 先发 start 文本帧
        ws.send_text(json.dumps({"type": "start"}))
        # 收到 ready
        ready = json.loads(ws.receive_text())
        assert ready["type"] == "ready"
        sid = ready["session_id"]
        # 收到 final（FakeAsr.start 已同步触发）
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

    with client.websocket_connect("/ws/audio") as ws:
        # 直接发音频帧（未 start），不应报错
        ws.send_bytes(b"\x00" * 8)

    app.dependency_overrides.clear()


def test_audio_ws_repeated_start_stops_old_session():
    """重复 start 帧：旧 ASR 会话必须先 stop（防泄漏 MiMo 的 httpx 连接池），再建新会话。"""
    _override_deps()
    _FakeAsr.last_instance = None
    client = TestClient(app)

    with client.websocket_connect("/ws/audio") as ws:
        ws.send_text(json.dumps({"type": "start"}))
        assert json.loads(ws.receive_text())["type"] == "ready"
        json.loads(ws.receive_text())  # final
        first = _FakeAsr.last_instance

        ws.send_text(json.dumps({"type": "start"}))
        assert json.loads(ws.receive_text())["type"] == "ready"
        second = _FakeAsr.last_instance

        assert first is not second
        assert first.stopped
        assert not second.stopped

    app.dependency_overrides.clear()
