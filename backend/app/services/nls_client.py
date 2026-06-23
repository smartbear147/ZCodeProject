"""阿里云 NLS 实时语音识别会话封装。

把 NLS SDK 的回调式 API 解耦成 on_partial / on_final 两个回调，
方便上层（路由层）处理和测试。

设计要点：
- _handle_message 是纯 JSON 解析+分发，可独立单测，不依赖 nls SDK。
- start/send_pcm/stop 才接触真实 SDK；nls 采用延迟导入，避免测试时强依赖。
"""

import json
from typing import Callable


class NlsAsrSession:
    def __init__(
        self,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        app_key: str,
        token: str,
        url: str = "wss://nls-gateway.cn-shanghai.aliyuncs.com/ws/v1",
    ) -> None:
        self._on_partial = on_partial
        self._on_final = on_final
        self._app_key = app_key
        self._token = token
        self._url = url
        self._nls = None  # nls.NlsClient 实例，start 后才有

    def _handle_message(self, message: str) -> None:
        """解析 NLS 返回的 JSON 消息，分发到 partial/final 回调。

        抽成独立方法便于单测（不依赖真实 SDK 连接）。
        """
        data = json.loads(message)
        name = data["header"]["name"]
        payload = data.get("payload", {}) or {}
        if name == "SentenceBegin":
            self._on_partial("")
        elif name == "TranscriptionResultChanged":
            self._on_partial(payload.get("result", ""))
        elif name == "SentenceEnd":
            self._on_final(payload.get("result", ""))
        # 其它事件（TaskFailed 等）忽略

    def start(self, on_close: Callable[[], None] | None = None) -> None:
        """建立 NLS 连接并开始转写。延迟导入 nls SDK。"""
        import nls  # 延迟导入：测试只测 _handle_message 时无需装 SDK

        def _cb(result, *_args):
            # nls SDK 把 JSON 字符串传给 on_metainfo 回调
            if isinstance(result, str):
                self._handle_message(result)

        self._nls = nls.NlsClient(
            url=self._url,
            token=self._token,
            on_metainfo=_cb,
            on_close=on_close or (lambda: None),
            on_open=lambda: None,
        )
        self._nls.start(
            aformat="pcm",
            sample_rate=16000,
            enable_intermediate_result=True,
            enable_punctuation_prediction=True,
            app_key=self._app_key,
        )

    def send_pcm(self, pcm_bytes: bytes) -> None:
        """喂入一段 16k s16 PCM。"""
        if self._nls is not None:
            self._nls.send_audio(pcm_bytes)

    def stop(self) -> None:
        """停止转写并关闭连接。"""
        if self._nls is not None:
            try:
                self._nls.stop()
            finally:
                self._nls = None
