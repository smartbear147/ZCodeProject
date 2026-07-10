"""通用 LLM 客户端（OpenAI 兼容接口）。

适用于任何 OpenAI 兼容的 API：智谱 GLM、小米 MiMo、DeepSeek、本地 Ollama 等。
只需在 .env 中配置 LLM_BASE_URL、LLM_API_KEY、LLM_MODEL 即可切换。
"""

from typing import Iterator, List

from openai import OpenAI


class LlmClient:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self._model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, messages: List[dict]) -> str:
        """同步生成，返回完整文本。"""
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=False,
        )
        return resp.choices[0].message.content

    def stream(self, messages: List[dict]) -> Iterator[str]:
        """流式生成，逐 token 产出文本片段；跳过空 delta。"""
        stream_resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
        )
        for chunk in stream_resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
