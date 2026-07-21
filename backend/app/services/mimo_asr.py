"""小米 MiMo ASR 分块转写会话封装（OpenAI 兼容接口）。

与 NlsAsrSession 实现相同的 start/send_pcm/stop 接口，使上层路由（audio.py）
可按 ASR_PROVIDER 在两者间切换。但内部策略根本不同：
  - 阿里云 NLS：流式 WebSocket，逐帧 send_pcm，服务端持续返回 partial/final。
  - MiMo ASR：整段转写，一段音频 base64 提交，返回该段文本；无"边传边识别"。
因此本类在 send_pcm 中累积 s16 mono PCM，每攒满 chunk_seconds 一段就提交一次
转写；stream 逐 delta 作为 partial（累积覆盖式）推送，整段完成作为 final。

参考文档: https://mimo.mi.com/docs/zh-CN/api/audio/Speech-Recognition

设计要点（与 nls_client 对齐）：
- _make_wav / _to_data_uri / _build_messages 是纯逻辑，可独立单测。
- send_pcm 在事件循环线程被同步调用，达阈值时用 loop.create_task 调度后台转写。
- 串行转写（_busy 标记）：一段未完成不切下一段，保证字幕顺序，代价是延迟累积。
- stop() 不丢尾音：调度 _shutdown 等进行中转写完成、flush 剩余 buffer 后再关闭客户端。
- 转写失败经 on_error 回调通知前端（每次会话只推一次），不静默。
"""

import asyncio
import base64
import io
import logging
import wave
from typing import Callable

from openai import AsyncOpenAI

logger = logging.getLogger("mimo_asr")


class MimoAsrSession:
    def __init__(
        self,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_error: Callable[[str], None] | None = None,
        *,
        api_key: str,
        model: str = "mimo-v2.5-asr",
        base_url: str = "https://api.xiaomimimo.com/v1",
        language: str = "auto",
        chunk_seconds: float = 4.0,
        sample_rate: int = 16000,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._on_partial = on_partial
        self._on_final = on_final
        self._on_error = on_error
        self._model = model
        self._language = language
        self._sample_rate = sample_rate
        # s16 mono: 每采样 2 字节；chunk_seconds 下限 1s，防止配置成 0/负数导致空调度
        self._chunk_bytes = int(sample_rate * 2 * max(chunk_seconds, 1.0))
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._buffer: bytearray = bytearray()
        self._busy = False
        self._tasks: set[asyncio.Task] = set()
        self._loop = loop
        self._stopping = False
        self._error_notified = False

    # ---------- 纯逻辑（可独立单测）----------

    def _make_wav(self, pcm: bytes) -> bytes:
        """把 s16 mono PCM 封装成 WAV 字节流。"""
        with io.BytesIO() as buf:
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(self._sample_rate)
                w.writeframes(pcm)
            return buf.getvalue()

    def _to_data_uri(self, wav: bytes) -> str:
        """WAV 字节 -> base64 Data URI（MiMo input_audio.data 格式）。"""
        return "data:audio/wav;base64," + base64.b64encode(wav).decode()

    def _build_messages(self, data_uri: str) -> list:
        """构造 chat completions 的 messages（input_audio 多模态内容）。"""
        return [
            {
                "role": "user",
                "content": [
                    {"type": "input_audio", "input_audio": {"data": data_uri}}
                ],
            }
        ]

    # ---------- 生命周期（接触 loop / 网络）----------

    def start(self, on_close: Callable[..., None] | None = None) -> None:
        """MiMo 为无状态 HTTP，无需建连；保留方法以对齐 AsrSession 接口。

        on_close 在 NLS 用于服务端断开重连，MiMo 无长连接，忽略。
        """
        logger.info(
            "MimoAsrSession started: chunk=%.1fs (%d bytes)",
            self._chunk_bytes / self._sample_rate / 2,
            self._chunk_bytes,
        )

    def send_pcm(self, pcm_bytes: bytes) -> None:
        """累积 s16 mono PCM；攒满一段就调度后台转写。"""
        if not pcm_bytes:
            return
        self._buffer.extend(pcm_bytes)
        self._maybe_flush()

    def _maybe_flush(self) -> None:
        """若 buffer 攒满一段且当前空闲，切出一段调度转写。"""
        if self._stopping:
            return
        if len(self._buffer) >= self._chunk_bytes and not self._busy:
            chunk = bytes(self._buffer[: self._chunk_bytes])
            del self._buffer[: self._chunk_bytes]
            self._busy = True
            task = self._loop.create_task(self._transcribe(chunk))
            self._tasks.add(task)
            task.add_done_callback(self._on_task_done)

    def _on_task_done(self, task: asyncio.Task) -> None:
        """转写结束后：清理任务集、解除 busy、尝试切下一段。"""
        self._tasks.discard(task)
        self._busy = False
        self._maybe_flush()

    async def _transcribe(self, pcm: bytes) -> None:
        """提交一段音频转写；stream 逐 delta -> on_partial，整段 -> on_final。"""
        try:
            wav = self._make_wav(pcm)
            data_uri = self._to_data_uri(wav)
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=self._build_messages(data_uri),
                extra_body={"asr_options": {"language": self._language}},
                stream=True,
            )
            accumulated = ""
            async for chunk in stream:
                try:
                    delta = chunk.choices[0].delta.content
                except (IndexError, AttributeError):
                    delta = None
                if delta:
                    accumulated += delta
                    self._on_partial(accumulated)
            if accumulated:
                self._on_final(accumulated)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("MimoAsrSession 转写失败")
            self._notify_error(f"MiMo 转写失败: {e}")

    def _notify_error(self, message: str) -> None:
        """转写失败通知前端；每次会话只推一次，避免持续失败时刷屏。"""
        if self._on_error is not None and not self._error_notified:
            self._error_notified = True
            self._on_error(message)

    def stop(self) -> None:
        """停止会话：调度后台收尾（flush 剩余 buffer -> 关闭 HTTP 客户端）。

        不取消进行中的转写——停采集时面试官最后那句话往往还在 buffer 或
        转写途中，丢掉就丢字幕；flush 出的 final 仍会落盘到会话字幕区。
        须在事件循环线程调用；stop 立即返回，清理由 _shutdown 后台完成。
        """
        if self._stopping:
            return
        self._stopping = True
        # 持有强引用（事件循环只持弱引用）并显式取异常，避免收尾失败静默丢失
        self._shutdown_task = self._loop.create_task(self._shutdown())
        self._shutdown_task.add_done_callback(self._on_shutdown_done)

    @staticmethod
    def _on_shutdown_done(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("MimoAsrSession 收尾失败: %s", exc, exc_info=exc)

    async def _shutdown(self) -> None:
        """等进行中的转写完成 -> 转写剩余不足一段的 buffer -> 关闭客户端。"""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
        if self._buffer:
            tail = bytes(self._buffer)
            self._buffer.clear()
            await self._transcribe(tail)
        self._busy = False
        await self._client.close()
