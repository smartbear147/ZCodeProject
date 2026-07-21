"""阿里云 NLS 实时语音识别会话封装。

基于官方 SDK 的 nls.NlsSpeechTranscriber(实时语音识别)类。
把 SDK 的多个回调式 API 解耦成 on_partial / on_final 两个回调,
方便上层(路由层)处理和测试。

参考文档:
- 实时语音识别 SDK: https://help.aliyun.com/zh/isi/developer-reference/sdk-for-python-2
- 获取 Token:       https://help.aliyun.com/zh/isi/getting-started/obtain-an-access-token

设计要点:
- _handle_message 是纯 JSON 解析+分发,可独立单测,不依赖 nls SDK。
- start/send_pcm/stop 才接触真实 SDK;nls 采用延迟导入,避免测试时强依赖。
"""

import json
import logging
from typing import Callable

logger = logging.getLogger("nls_client")

# 官方文档指定的网关地址
DEFAULT_URL = "wss://nls-gateway.cn-shanghai.aliyuncs.com/ws/v1"


class NlsAsrSession:
    def __init__(
        self,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        app_key: str,
        token: str,
        url: str = DEFAULT_URL,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._on_partial = on_partial
        self._on_final = on_final
        self._on_error = on_error
        self._app_key = app_key
        self._token = token
        self._url = url
        self._transcriber = None  # nls.NlsSpeechTranscriber 实例,start 后才有

    def _handle_message(self, message: str) -> None:
        """解析 NLS 返回的 JSON 消息,分发到 partial/final 回调。

        抽成独立方法便于单测(不依赖真实 SDK 连接)。
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
        elif name == "TaskFailed":
            logger.warning("NLS TaskFailed: %s", message)
            # SDK 的 on_error 回调不可靠，TaskFailed 是服务端明确送达的失败，通知前端
            if self._on_error is not None:
                reason = data["header"].get("status_text", "未知错误")
                self._on_error(f"NLS 识别失败: {reason}")
        elif name == "RecognitionStarted":
            logger.warning("NLS RecognitionStarted (识别已开始)")
        elif name == "TranscriptionCompleted":
            logger.warning("NLS TranscriptionCompleted")
        # 其它事件忽略

    def start(self, on_close: Callable[..., None] | None = None) -> None:
        """建立 NLS 连接并开始转写。延迟导入 nls SDK。

        SDK 各回调签名:第一个参数是消息(JSON 字符串)。
        on_close 签名不同:只有 *args,没有消息。
        """
        import nls  # 延迟导入:测试只测 _handle_message 时无需 SDK 真实运行

        def _on_msg(message, *_args):
            """通用消息回调:SDK 把 JSON 字符串作为第一个参数传入。"""
            if isinstance(message, str):
                self._handle_message(message)

        def _on_close(*_args):
            logger.warning("NLS on_close: 连接关闭")
            if on_close:
                on_close()

        def _on_error(message, *_args):
            logger.warning("NLS on_error 回调: %s", message)

        logger.warning("creating NlsSpeechTranscriber, appkey=%s, token_len=%d",
                       self._app_key, len(self._token))
        self._transcriber = nls.NlsSpeechTranscriber(
            url=self._url,
            token=self._token,
            appkey=self._app_key,
            on_start=_on_msg,
            on_result_changed=_on_msg,
            on_sentence_begin=_on_msg,
            on_sentence_end=_on_msg,
            on_completed=_on_msg,
            on_error=_on_error,
            on_close=_on_close,
            callback_args=[],
        )
        self._transcriber.start(
            aformat="pcm",
            sample_rate=16000,
            enable_intermediate_result=True,
            enable_punctuation_prediction=True,
            enable_inverse_text_normalization=True,
        )

    def send_pcm(self, pcm_bytes: bytes) -> None:
        """喂入一段 16k s16 PCM。"""
        if self._transcriber is not None:
            self._transcriber.send_audio(pcm_bytes)

    def stop(self) -> None:
        """停止转写并关闭连接。"""
        if self._transcriber is not None:
            try:
                self._transcriber.stop()
            finally:
                self._transcriber = None
