"""智谱 GLM 封装：同步生成 + 流式生成。"""

from typing import Iterator, List

from zhipuai import ZhipuAI


class LlmClient:
    def __init__(self, api_key: str, model: str) -> None:
        self._model = model
        self._client = ZhipuAI(api_key=api_key)

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
