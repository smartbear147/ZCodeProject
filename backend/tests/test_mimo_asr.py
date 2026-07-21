"""测试 MiMo ASR 会话的纯逻辑（WAV 封装 / Data URI / 请求体 / buffer 切分）+ _transcribe 流式迭代。

与 test_nls_client.py 风格一致：不依赖真实网络。_transcribe 用 mock 的 stream 验证
delta 累积 -> on_partial、整段 -> on_final 的逻辑（端到端合成音调无法覆盖，因为
MiMo 流式对无语义音频返回空 content）。
"""

import base64
import wave
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from app.services.mimo_asr import MimoAsrSession


def _make_session(chunk_seconds=4.0, sample_rate=16000):
    cb = MagicMock()
    loop = MagicMock()

    # mock 的 create_task 不会执行协程，主动关闭避免 "never awaited" 警告
    def _noop_create_task(coro):
        coro.close()
        return MagicMock()

    loop.create_task.side_effect = _noop_create_task
    session = MimoAsrSession(
        on_partial=cb.on_partial,
        on_final=cb.on_final,
        on_error=cb.on_error,
        api_key="k",
        model="mimo-v2.5-asr",
        base_url="https://example/v1",
        language="auto",
        chunk_seconds=chunk_seconds,
        sample_rate=sample_rate,
        loop=loop,
    )
    return session, cb, loop


def _silence_pcm(seconds, rate=16000):
    """生成 N 秒静音的 s16 mono PCM。"""
    return b"\x00\x00" * (rate * seconds)


def _delta_chunk(content):
    """构造一个流式 chunk：choices[0].delta.content = content。"""
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content))]
    )


def test_make_wav_produces_valid_wav():
    session, _, _ = _make_session()
    wav = session._make_wav(_silence_pcm(1))
    with wave.open(BytesIO(wav), "rb") as r:
        assert r.getnchannels() == 1
        assert r.getsampwidth() == 2
        assert r.getframerate() == 16000
        assert r.getnframes() == 16000


def test_to_data_uri_has_prefix_and_is_decodable():
    session, _, _ = _make_session()
    wav = session._make_wav(_silence_pcm(1))
    uri = session._to_data_uri(wav)
    assert uri.startswith("data:audio/wav;base64,")
    decoded = base64.b64decode(uri.split(",", 1)[1])
    assert decoded == wav  # base64 可逆


def test_build_messages_structure():
    session, _, _ = _make_session()
    msgs = session._build_messages("data:audio/wav;base64,AAA=")
    assert msgs == [
        {
            "role": "user",
            "content": [
                {"type": "input_audio", "input_audio": {"data": "data:audio/wav;base64,AAA="}}
            ],
        }
    ]


def test_chunk_bytes_calculation():
    session, _, _ = _make_session(chunk_seconds=4.0, sample_rate=16000)
    assert session._chunk_bytes == 16000 * 2 * 4


def test_send_pcm_accumulates_below_threshold():
    session, cb, loop = _make_session(chunk_seconds=4.0)
    session.send_pcm(_silence_pcm(1))  # 不足 4 秒阈值
    loop.create_task.assert_not_called()
    cb.on_partial.assert_not_called()
    assert len(session._buffer) == 16000 * 2  # 1 秒留在 buffer


def test_send_pcm_triggers_at_threshold():
    session, cb, loop = _make_session(chunk_seconds=4.0)
    session.send_pcm(_silence_pcm(4))  # 一次给足 4 秒
    loop.create_task.assert_called_once()
    assert len(session._buffer) == 0  # 切走 4 秒，buffer 空


def test_send_pcm_does_not_trigger_when_busy():
    session, cb, loop = _make_session(chunk_seconds=4.0)
    session.send_pcm(_silence_pcm(4))  # 触发，busy=True
    assert loop.create_task.call_count == 1
    session.send_pcm(_silence_pcm(5))  # busy 中，只累积不再触发
    assert loop.create_task.call_count == 1
    assert len(session._buffer) == 16000 * 2 * 5


def test_empty_pcm_ignored():
    session, cb, loop = _make_session()
    session.send_pcm(b"")
    loop.create_task.assert_not_called()
    assert len(session._buffer) == 0


async def test_transcribe_streams_partial_and_final():
    """_transcribe 迭代 stream：逐非空 delta -> on_partial（累积覆盖），整段 -> on_final。"""
    session, cb, loop = _make_session()
    session._client = MagicMock()

    async def fake_stream():
        for c in [_delta_chunk("你"), _delta_chunk("好"), _delta_chunk(""), _delta_chunk(None)]:
            yield c

    session._client.chat.completions.create = AsyncMock(return_value=fake_stream())

    await session._transcribe(_silence_pcm(1))

    cb.on_partial.assert_any_call("你")
    cb.on_partial.assert_any_call("你好")
    cb.on_final.assert_called_once_with("你好")


def test_chunk_seconds_clamped_to_minimum():
    """chunk_seconds 配成 0/负数时下限 clamp 到 1s，避免空调度。"""
    session, _, _ = _make_session(chunk_seconds=0)
    assert session._chunk_bytes == 16000 * 2 * 1


def test_on_task_done_chains_next_chunk():
    """一段转写完成（busy 复位）后，buffer 里攒够的下一段应立即链式切出。"""
    session, cb, loop = _make_session(chunk_seconds=4.0)
    session.send_pcm(_silence_pcm(4))
    assert loop.create_task.call_count == 1
    session.send_pcm(_silence_pcm(4))  # busy 中，只累积
    session._on_task_done(MagicMock())  # 第一段完成 → 链式切第二段
    assert loop.create_task.call_count == 2


def test_stop_is_idempotent_and_blocks_new_flush():
    """stop 幂等；stopping 后 _maybe_flush 不再调度新任务（buffer 留给 _shutdown）。"""
    session, _, loop = _make_session(chunk_seconds=4.0)
    session.stop()
    assert loop.create_task.call_count == 1  # _shutdown 已调度
    session.stop()
    assert loop.create_task.call_count == 1  # 不重复调度
    session.send_pcm(_silence_pcm(4))  # 达阈值也不再触发新转写
    assert loop.create_task.call_count == 1
    assert len(session._buffer) == 16000 * 2 * 4


async def test_shutdown_flushes_tail_and_closes_client():
    """_shutdown 转写不足一段的尾部 buffer（不丢尾音），最后关闭 HTTP 客户端。"""
    session, cb, _ = _make_session()
    session._client = MagicMock()
    session._client.close = AsyncMock()

    async def fake_stream():
        yield _delta_chunk("尾部")

    session._client.chat.completions.create = AsyncMock(return_value=fake_stream())
    session.send_pcm(_silence_pcm(2))  # 不足 4s，留在 buffer
    session._stopping = True  # 模拟 stop() 已置位（stop 本身走 mocked loop，这里直接驱动 _shutdown）
    await session._shutdown()

    cb.on_final.assert_called_once_with("尾部")
    assert len(session._buffer) == 0
    session._client.close.assert_awaited_once()


async def test_transcribe_failure_notifies_on_error_once():
    """转写失败通过 on_error 通知前端；同一会话连续失败只推一次，不刷屏。"""
    session, cb, _ = _make_session()
    session._client = MagicMock()
    session._client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))

    await session._transcribe(_silence_pcm(1))
    await session._transcribe(_silence_pcm(1))

    cb.on_error.assert_called_once()
    assert "boom" in cb.on_error.call_args[0][0]
    cb.on_final.assert_not_called()
