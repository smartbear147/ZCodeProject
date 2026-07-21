"""音频 + 字幕 WebSocket 路由。

协议：
- 前端首帧（文本）: {"type":"start","session_id":"<可选>"}
- 前端后续帧: 二进制音频（48k float32 pcm）
- 后端 -> 前端:
    {"type":"ready","session_id":"..."} |
    {"type":"partial","text":"..."} |
    {"type":"final","text":"...","session_id":"..."} |
    {"type":"error","message":"..."}

ASR 回调可能来自独立线程（阿里云 NLS SDK）或事件循环（MiMo async task），
统一通过 run_coroutine_threadsafe 调度回事件循环发送，两家通用。
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.config import Settings, get_settings
from app.deps import get_asr_factory, get_session_store
from app.services.asr_base import AsrSession
from app.services.resampler import resample_to_16k_s16
from app.services.session import SessionStore

router = APIRouter()
logger = logging.getLogger("audio_ws")


@router.websocket("/ws/audio")
async def audio_ws(
    websocket: WebSocket,
    settings: Settings = Depends(get_settings),
    store: SessionStore = Depends(get_session_store),
    asr_factory=Depends(get_asr_factory),
) -> None:
    await websocket.accept()
    logger.info("ws connected")

    loop = asyncio.get_running_loop()
    session = None
    asr_session: AsrSession | None = None

    # 标记 ASR 是否已主动断开，避免 finally 里重复 stop()
    asr_closed = False

    def _send(payload: dict) -> None:
        """从任意线程把 JSON 消息调度到事件循环发送给前端。"""
        text = json.dumps(payload, ensure_ascii=False)

        async def _do_send() -> None:
            try:
                await websocket.send_text(text)
            except RuntimeError:
                # WS 已关闭（如 stop 后尾部 flush 的字幕推送）；字幕已落盘，跳过即可
                logger.debug("WS 已关闭，跳过推送: %s", text[:80])

        asyncio.run_coroutine_threadsafe(_do_send(), loop)

    try:
        while True:
            try:
                msg = await websocket.receive()
            except WebSocketDisconnect:
                logger.info("ws disconnected by client")
                break
            # Starlette 可能把 disconnect 作为消息返回而非抛异常
            if msg.get("type") == "websocket.disconnect":
                logger.info("ws disconnect message")
                break
            if "text" in msg:
                data = json.loads(msg["text"])
                if data.get("type") == "start":
                    if asr_session is not None:
                        # 重复 start：先停掉旧会话，避免泄漏（MiMo 的 httpx 连接池）
                        asr_session.stop()
                        asr_closed = False
                    sid = data.get("session_id")
                    session = store.get_or_create(sid) if sid else store.create()
                    try:
                        asr_session = asr_factory(
                            on_partial=lambda t: _send({"type": "partial", "text": t}),
                            on_final=_make_on_final(session, store, _send),
                            loop=loop,
                            on_error=lambda m: _send({"type": "error", "message": m}),
                        )
                    except Exception as e:
                        logger.exception("ASR 会话创建失败")
                        _send({"type": "error", "message": f"ASR 初始化失败: {e}"})
                        continue
                    # 先通知前端就绪，再启动 ASR（避免回调早于 ready 触发）
                    _send({"type": "ready", "session_id": session.session_id})
                    try:
                        def _on_asr_close() -> None:
                            """ASR 服务端主动断开时自动重连（仅 NLS 会触发；MiMo 无长连接不会调用）。"""
                            nonlocal asr_closed, asr_session
                            asr_closed = True
                            logger.warning("ASR 连接已断开，尝试自动重连")
                            try:
                                new_session = asr_factory(
                                    on_partial=lambda t: _send({"type": "partial", "text": t}),
                                    on_final=_make_on_final(session, store, _send),
                                    loop=loop,
                                    on_error=lambda m: _send({"type": "error", "message": m}),
                                )
                                new_session.start(on_close=_on_asr_close)
                                asr_session = new_session
                                asr_closed = False
                                logger.info("ASR 自动重连成功")
                            except Exception:
                                logger.exception("ASR 自动重连失败")
                                _send({"type": "error", "message": "ASR 连接已断开，请重新开始采集"})

                        asr_session.start(on_close=_on_asr_close)
                        logger.info("asr start() returned ok")
                    except Exception as e:  # ASR 启动失败
                        logger.exception("asr start() raised")
                        _send({"type": "error", "message": f"ASR 启动失败: {e}"})
                        await websocket.close()
                        return
            elif "bytes" in msg:
                if asr_session is None:
                    logger.info("收到音频帧但 asr_session 还没建立,丢弃")
                    continue  # 没 start，丢弃音频
                pcm16 = resample_to_16k_s16(
                    msg["bytes"], in_rate=settings.input_sample_rate
                )
                logger.debug("收到音频帧 输入 %d 字节 -> 重采样 %d 字节",
                             len(msg["bytes"]), len(pcm16))
                try:
                    asr_session.send_pcm(pcm16)
                except Exception as e:
                    logger.exception("send_pcm failed")
                    _send({"type": "error", "message": f"音频发送失败: {e}"})
    except Exception:
        logger.exception("audio_ws loop crashed")
    finally:
        logger.info("ws closing, stopping asr")
        if asr_session is not None and not asr_closed:
            asr_session.stop()


def _make_on_final(session, store: SessionStore, send_fn):
    """构造 final 回调：累积到 session 并推送给前端。"""

    def on_final(text: str) -> None:
        if session is None:
            return
        session.add_subtitle(text)
        store.save(session.session_id)  # 字幕更新落盘
        send_fn(
            {"type": "final", "text": text, "session_id": session.session_id}
        )

    return on_final
