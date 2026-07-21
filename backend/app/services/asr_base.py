"""ASR 会话统一接口（Protocol）。

阿里云 NlsAsrSession 与 MiMo MimoAsrSession 都实现此接口，
使上层路由（audio.py）可按 ASR_PROVIDER 在两者间切换，无需改动业务逻辑。

接口与 NlsAsrSession 现有方法保持一致：start / send_pcm / stop。
"""

from typing import Callable, Protocol


class AsrSession(Protocol):
    """语音识别会话的统一接口（实时流式或分块转写均适用）。

    线程契约：start / send_pcm / stop 都必须在构造时传入的事件循环所在线程
    调用（MimoAsrSession 内部直接 loop.create_task；NlsAsrSession 虽任意线程
    安全，但上层统一按循环线程调用）。反向推送（partial/final/error 回调）
    则可能来自任意线程，路由层需用 run_coroutine_threadsafe 桥回循环。
    """

    def start(self, on_close: Callable[..., None] | None = None) -> None: ...

    def send_pcm(self, pcm_bytes: bytes) -> None: ...

    def stop(self) -> None: ...
