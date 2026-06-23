"""音频 + 字幕 WebSocket 路由。

协议：
- 前端首帧（文本）: {"type":"start","session_id":"<可选>"}
- 前端后续帧: 二进制音频（48k float32 pcm）
- 后端 -> 前端:
    {"type":"ready","session_id":"..."} |
    {"type":"partial","text":"..."} |
    {"type":"final","text":"...","session_id":"..."} |
    {"type":"error","message":"..."}

NLS SDK 的回调在独立线程触发，websocket 发送是协程，
所以通过 run_coroutine_threadsafe 调度回事件循环。
"""

import asyncio
import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.config import Settings, get_settings
from app.deps import get_session_store, get_token_provider
from app.services.nls_client import NlsAsrSession
from app.services.resampler import resample_to_16k_s16
from app.services.session import SessionStore

router = APIRouter()


@router.websocket("/ws/audio")
async def audio_ws(
    websocket: WebSocket,
    settings: Settings = Depends(get_settings),
    store: SessionStore = Depends(get_session_store),
    token_provider=Depends(get_token_provider),
) -> None:
    await websocket.accept()

    loop = asyncio.get_running_loop()
    session = None
    nls_session: NlsAsrSession | None = None

    def _send(payload: dict) -> None:
        """从任意线程把 JSON 消息调度到事件循环发送给前端。"""
        text = json.dumps(payload, ensure_ascii=False)
        asyncio.run_coroutine_threadsafe(websocket.send_text(text), loop)

    try:
        while True:
            try:
                msg = await websocket.receive()
            except WebSocketDisconnect:
                break
            # Starlette 可能把 disconnect 作为消息返回而非抛异常
            if msg.get("type") == "websocket.disconnect":
                break
            if "text" in msg:
                data = json.loads(msg["text"])
                if data.get("type") == "start":
                    sid = data.get("session_id")
                    session = store.get_or_create(sid) if sid else store.create()
                    token = token_provider.get_token()
                    nls_session = NlsAsrSession(
                        on_partial=lambda t: _send({"type": "partial", "text": t}),
                        on_final=_make_on_final(session, store, _send),
                        app_key=settings.aliyun_nls_app_key,
                        token=token,
                    )
                    # 先通知前端就绪，再启动 ASR（避免 NLS 回调早于 ready 触发）
                    _send({"type": "ready", "session_id": session.session_id})
                    try:
                        nls_session.start()
                    except Exception as e:  # ASR 启动失败
                        _send({"type": "error", "message": f"ASR 启动失败: {e}"})
                        await websocket.close()
                        return
            elif "bytes" in msg:
                if nls_session is None:
                    continue  # 未 start，丢弃音频
                pcm16 = resample_to_16k_s16(
                    msg["bytes"], in_rate=settings.input_sample_rate
                )
                nls_session.send_pcm(pcm16)
    finally:
        if nls_session is not None:
            nls_session.stop()


def _make_on_final(session, store: SessionStore, send_fn):
    """构造 final 回调：累积到 session 并推给前端。"""

    def on_final(text: str) -> None:
        if session is None:
            return
        session.append_final(text)
        send_fn(
            {"type": "final", "text": text, "session_id": session.session_id}
        )

    return on_final
