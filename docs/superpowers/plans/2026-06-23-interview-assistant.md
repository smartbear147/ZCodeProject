# 面试助手 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Web 应用，求职者在腾讯会议面试时实时把面试官的话转写为文本，按按钮后用智谱 GLM 生成回答建议，并可继续追问。

**Architecture:** 前端 React + Vite 通过 `getUserMedia` 采集系统音频（BlackHole 虚拟声卡）→ WebSocket 传给 FastAPI 后端 → 后端重采样为 16k PCM → 转发到阿里云 NLS 实时流式识别 → 字幕回推前端。用户按"生成建议"按钮，后端把当前轮次累积文本送给智谱 GLM 同步生成建议；追问通过 SSE 流式返回。会话状态存内存。

**Tech Stack:** Python 3.11 / FastAPI / WebSockets / `nls` (阿里云 NLS SDK) / `zhipuai` SDK / `audioop`-based resample / `pytest` · React 18 + Vite + TypeScript / `AudioWorklet` / WebSocket / EventSource (SSE) / Vitest

---

## 文件结构总览

```
project/
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app + 路由挂载
│   │   ├── config.py                # 配置加载（env）
│   │   ├── deps.py                  # 依赖注入（get_session_store）
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── audio.py             # WS: 音频上行 + 字幕下行
│   │   │   └── chat.py              # REST: 生成建议；SSE: 追问
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── resampler.py         # 48k float32 → 16k s16 pcm
│   │   │   ├── nls_client.py        # 阿里云 NLS WebSocket 桥接
│   │   │   ├── token_provider.py    # 阿里云 NLS Token 刷新
│   │   │   ├── llm.py               # 智谱 GLM 同步 + 流式
│   │   │   ├── session.py           # InterviewSession + Store（内存）
│   │   │   └── suggest.py           # 组装 prompt + 调 LLM
│   │   ├── prompts.py               # SYSTEM_PROMPT 常量
│   │   └── schemas.py               # Pydantic 模型
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_resampler.py
│       ├── test_session.py
│       ├── test_llm.py
│       ├── test_suggest.py
│       ├── test_token_provider.py
│       ├── test_nls_client.py
│       ├── test_audio_route.py
│       └── test_chat_route.py
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   ├── asrSocket.ts
│       │   └── chat.ts
│       ├── hooks/
│       │   ├── useAudioCapture.ts
│       │   ├── useSubtitle.ts
│       │   └── useChat.ts
│       ├── components/
│       │   ├── SubtitlePanel.tsx
│       │   ├── SuggestPanel.tsx
│       │   └── Controls.tsx
│       ├── audio/
│       │   └── capture-worklet.ts   # AudioWorkletProcessor
│       └── types.ts
└── docs/
    ├── superpowers/specs/2026-06-23-interview-assistant-design.md
    ├── superpowers/plans/2026-06-23-interview-assistant.md
    └── SETUP.md                     # BlackHole 安装配置 + 运行说明
```

---

## Task 1: 后端项目骨架与配置

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: 写 `pyproject.toml`**

```toml
[project]
name = "interview-assistant-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.110",
  "uvicorn[standard]>=0.29",
  "websockets>=12.0",
  "zhipuai>=2.1.0",
  "aliyun-python-sdk-core>=2.15.0",
  "nls @ git+https://github.com/aliyun/alibabacloud-nls-python-sdk.git",
  "pydantic>=2.6",
  "pydantic-settings>=2.2",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23", "httpx>=0.27"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: 写 `.env.example`**

```env
# 阿里云 NLS
ALIYUN_ACCESS_KEY_ID=your_access_key_id
ALIYUN_ACCESS_KEY_SECRET=your_access_key_secret
ALIYUN_NLS_APP_KEY=your_nls_app_key
ALIYUN_NLS_REGION=cn-shanghai

# 智谱 GLM
ZHIPU_API_KEY=your_zhipu_api_key
ZHIPU_MODEL=glm-4-plus
```

- [ ] **Step 3: 写 `app/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 阿里云 NLS
    aliyun_access_key_id: str = ""
    aliyun_access_key_secret: str = ""
    aliyun_nls_app_key: str = ""
    aliyun_nls_region: str = "cn-shanghai"

    # 智谱 GLM
    zhipu_api_key: str = ""
    zhipu_model: str = "glm-4-plus"

    # 音频
    input_sample_rate: int = 48000
    output_sample_rate: int = 16000

    class Config:
        env_file = ".env"
        env_prefix = ""


def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: 写 `app/main.py`（最小骨架，后续 task 填路由）**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Interview Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 5: 写 `tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```

- [ ] **Step 6: 写失败测试 `tests/test_config.py`**

```python
from app.config import get_settings


def test_default_model_is_glm_4_plus():
    s = get_settings()
    assert s.zhipu_model == "glm-4-plus"


def test_default_sample_rates():
    s = get_settings()
    assert s.input_sample_rate == 48000
    assert s.output_sample_rate == 16000
```

- [ ] **Step 7: 安装依赖并跑测试**

Run: `cd backend && pip install -e ".[dev]" && pytest tests/test_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 8: 跑 health 接口冒烟**

Run: `cd backend && python -c "from app.main import app; from fastapi.testclient import TestClient; c=TestClient(app); print(c.get('/health').json())"`
Expected: `{'status': 'ok'}`

- [ ] **Step 9: Commit**

```bash
git init 2>/dev/null; git add backend/
git commit -m "feat(backend): project skeleton, config, health endpoint"
```

---

## Task 2: 音频重采样模块（TDD）

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/resampler.py`
- Create: `backend/tests/test_resampler.py`

**职责：** 把浏览器来的 48kHz Float32 PCM 转成阿里云 NLS 要求的 16kHz 16-bit 单声道 PCM。逐帧（chunk）处理，无状态。

- [ ] **Step 1: 写失败测试 `tests/test_resampler.py`**

```python
import math
import struct

from app.services.resampler import resample_to_16k_s16


def _make_float32_frames(freq_hz: float, duration_s: float, in_rate: int) -> bytes:
    """生成一个纯正弦波的 float32 PCM 字节（单声道）。"""
    n = int(duration_s * in_rate)
    frames = []
    for i in range(n):
        t = i / in_rate
        sample = math.sin(2 * math.pi * freq_hz * t)
        frames.append(struct.pack("<f", sample))
    return b"".join(frames)


def test_resample_halves_sample_count():
    """48k -> 16k: 样本数应为输入的 1/3。"""
    pcm_in = _make_float32_frames(440.0, 0.1, 48000)  # 4800 samples
    pcm_out = resample_to_16k_s16(pcm_in, in_rate=48000)
    # s16 = 2 bytes/sample
    assert len(pcm_out) // 2 == 4800 // 3


def test_resample_output_is_s16_range():
    """输出应裁剪到 int16 范围。"""
    # 振幅 5.0（超出 1.0），裁剪后应等于 int16 max
    n = 480
    pcm_in = struct.pack("<" + "f" * n, *([5.0] * n))
    pcm_out = resample_to_16k_s16(pcm_in, in_rate=48000)
    first_sample = struct.unpack("<h", pcm_out[:2])[0]
    assert first_sample == 32767


def test_resample_empty_input():
    assert resample_to_16k_s16(b"", in_rate=48000) == b""
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_resampler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.resampler'`

- [ ] **Step 3: 写最小实现 `app/services/resampler.py`**

```python
"""音频重采样：浏览器 48kHz Float32 PCM -> 16kHz 16-bit 单声道 PCM。

无状态、逐帧处理，便于流式转码。
"""

import audioop
import struct


def resample_to_16k_s16(pcm_in: bytes, in_rate: int = 48000) -> bytes:
    """把 float32 单声道 PCM 转成 16kHz s16 单声道 PCM。

    Args:
        pcm_in: float32 LE 字节流。
        in_rate: 输入采样率（默认 48000）。

    Returns:
        16kHz、16-bit 单声道 PCM 字节。
    """
    if not pcm_in:
        return b""

    # 1. float32 -> s16
    n_samples = len(pcm_in) // 4
    floats = struct.unpack("<%df" % n_samples, pcm_in)
    # 裁剪到 [-1.0, 1.0] 再放大到 int16
    ints = []
    for f in floats:
        f = max(-1.0, min(1.0, f))
        ints.append(int(f * 32767))
    s16_bytes = struct.pack("<%dh" % n_samples, *ints)

    # 2. 降采样到 16k（audioop: 1 channel = mono）
    converted, _state = audioop.ratecv(s16_bytes, 2, 1, in_rate, 16000, None)
    return converted
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_resampler.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/resampler.py backend/tests/test_resampler.py
git commit -m "feat(backend): audio resampler 48k float32 -> 16k s16"
```

---

## Task 3: 会话状态管理（TDD）

**Files:**
- Create: `backend/app/services/session.py`
- Create: `backend/app/schemas.py`
- Create: `backend/tests/test_session.py`

**职责：** 内存里管理 `InterviewSession`：当前轮次累积文本、历史轮次、追加定稿、生成建议后的轮转、清空。

- [ ] **Step 1: 写 `app/schemas.py`（Pydantic 模型）**

```python
from pydantic import BaseModel


class Turn(BaseModel):
    """一轮问答。"""
    question: str
    suggestion: str


class SuggestRequest(BaseModel):
    session_id: str


class SuggestResponse(BaseModel):
    session_id: str
    suggestion: str
    question: str


class AskRequest(BaseModel):
    session_id: str
    message: str
```

- [ ] **Step 2: 写失败测试 `tests/test_session.py`**

```python
from app.services.session import SessionStore


def test_new_session_has_empty_state():
    store = SessionStore()
    s = store.create()
    assert s.current_turn_text == ""
    assert s.history_turns == []


def test_append_final_accumulates_into_current_turn():
    store = SessionStore()
    s = store.create()
    s.append_final("你好")
    s.append_final("请自我介绍")
    assert s.current_turn_text == "你好\n请自我介绍"


def test_finalize_turn_moves_to_history_and_clears_current():
    store = SessionStore()
    s = store.create()
    s.append_final("讲讲项目")
    s.finalize_turn(suggestion="用 STAR 讲...")
    assert s.current_turn_text == ""
    assert len(s.history_turns) == 1
    assert s.history_turns[0].question == "讲讲项目"
    assert s.history_turns[0].suggestion == "用 STAR 讲..."


def test_clear_history_empties_history_only():
    store = SessionStore()
    s = store.create()
    s.append_final("q1")
    s.finalize_turn(suggestion="a1")
    s.append_final("q2 current")
    s.clear_history()
    assert s.history_turns == []
    # 当前轮次不动
    assert s.current_turn_text == "q2 current"
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `pytest tests/test_session.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: 写实现 `app/services/session.py`**

```python
"""会话状态管理（内存）。本期单进程、不持久化。"""

from __future__ import annotations

import uuid
from typing import Dict, List

from app.schemas import Turn


class InterviewSession:
    """一场面试的一个会话。"""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.current_turn_text: str = ""
        self.history_turns: List[Turn] = []

    def append_final(self, text: str) -> None:
        """追加一句定稿字幕到当前轮次。"""
        text = text.strip()
        if not text:
            return
        if self.current_turn_text:
            self.current_turn_text += "\n" + text
        else:
            self.current_turn_text = text

    def finalize_turn(self, suggestion: str) -> None:
        """把当前轮次结转为历史，记录建议，清空当前轮次。"""
        self.history_turns.append(
            Turn(question=self.current_turn_text, suggestion=suggestion)
        )
        self.current_turn_text = ""


class SessionStore:
    """按 session_id 索引的会话存储（内存字典）。"""

    def __init__(self) -> None:
        self._sessions: Dict[str, InterviewSession] = {}

    def create(self) -> InterviewSession:
        sid = uuid.uuid4().hex
        s = InterviewSession(sid)
        self._sessions[sid] = s
        return s

    def get(self, session_id: str) -> InterviewSession | None:
        return self._sessions.get(session_id)

    def get_or_create(self, session_id: str) -> InterviewSession:
        return self._sessions.get(session_id) or self.create()

    def clear_history(self, session_id: str) -> None:
        s = self.get(session_id)
        if s:
            s.history_turns = []
```

**注意：** `clear_history` 在 `InterviewSession` 上也要有方法（测试里直接调了 `s.clear_history()`）。补充：

```python
# 追加到 InterviewSession 类里
    def clear_history(self) -> None:
        """清空历史轮次，但保留当前正在进行的轮次。"""
        self.history_turns = []
```

（`SessionStore.clear_history` 调用 `s.clear_history()`）

- [ ] **Step 5: 运行测试，确认通过**

Run: `pytest tests/test_session.py -v`
Expected: PASS (4 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas.py backend/app/services/session.py backend/tests/test_session.py
git commit -m "feat(backend): in-memory interview session store"
```

---

## Task 4: System Prompt 与智谱 GLM 封装（TDD）

**Files:**
- Create: `backend/app/prompts.py`
- Create: `backend/app/services/llm.py`
- Create: `backend/tests/test_llm.py`

**职责：** 封装智谱 GLM 的同步生成（建议）和流式生成（追问），用 mock SDK 测。

- [ ] **Step 1: 写 `app/prompts.py`**

```python
SYSTEM_PROMPT = """你是一位资深面试教练，帮助求职者应对面试。

任务：针对面试官的问题，给出回答建议。要求：
1. 先简要点出面试官在考察什么
2. 给出 1-2 个回答方向/要点（建议用 STAR 结构：情境-任务-行动-结果）
3. 如适合，给一个简短的回答示范开头
4. 不要替求职者编造具体经历或数据，只给思路和框架

特别注意：
- 如果面试官的话只是寒暄/闲聊（如"你今天怎么样""路上堵车吗"），不要给正式回答建议，只回复"[非正式问题，闲聊即可]"。
"""
```

- [ ] **Step 2: 写失败测试 `tests/test_llm.py`**

```python
from unittest.mock import MagicMock, patch

from app.services.llm import LlmClient


@patch("app.services.llm.ZhipuAI")
def test_generate_returns_full_text(mock_zhipu_cls):
    mock_client = MagicMock()
    mock_zhipu_cls.return_value = mock_client
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="建议正文"))]
    mock_client.chat.completions.create.return_value = mock_resp

    llm = LlmClient(api_key="fake", model="glm-4-plus")
    text = llm.generate(messages=[{"role": "user", "content": "hi"}])
    assert text == "建议正文"
    mock_client.chat.completions.create.assert_called_once()
    kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "glm-4-plus"
    assert kwargs["stream"] is False


@patch("app.services.llm.ZhipuAI")
def test_stream_returns_chunks(mock_zhipu_cls):
    mock_client = MagicMock()
    mock_zhipu_cls.return_value = mock_client

    def fake_stream(_messages, _model, _stream):
        for chunk_text in ["你", "好", "呀"]:
            m = MagicMock()
            m.choices = [MagicMock(delta=MagicMock(content=chunk_text))]
            yield m

    mock_client.chat.completions.create.side_effect = fake_stream

    llm = LlmClient(api_key="fake", model="glm-4-plus")
    chunks = list(llm.stream(messages=[{"role": "user", "content": "hi"}]))
    assert "".join(chunks) == "你好呀"
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: 写实现 `app/services/llm.py`**

```python
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
        """流式生成，逐 token 产出文本片段。"""
        stream_resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
        )
        for chunk in stream_resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
```

- [ ] **Step 5: 运行测试，确认通过**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add backend/app/prompts.py backend/app/services/llm.py backend/tests/test_llm.py
git commit -m "feat(backend): system prompt + zhipu glm client wrapper"
```

---

## Task 5: 生成建议业务逻辑（TDD）

**Files:**
- Create: `backend/app/services/suggest.py`
- Create: `backend/tests/test_suggest.py`

**职责：** 组装 messages（System + 历史轮次 + 当前问题），调 LLM 同步生成，返回建议文本。

- [ ] **Step 1: 写失败测试 `tests/test_suggest.py`**

```python
from unittest.mock import MagicMock

from app.prompts import SYSTEM_PROMPT
from app.services.session import SessionStore
from app.services.suggest import SuggestService


def _fake_llm(return_text: str) -> MagicMock:
    llm = MagicMock()
    llm.generate.return_value = return_text
    return llm


def test_build_messages_for_first_turn():
    store = SessionStore()
    s = store.create()
    s.append_final("讲讲你最有挑战的项目")
    svc = SuggestService(llm=_fake_llm("建议"), store=store)

    msgs = svc.build_messages(s)

    assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert msgs[-1]["content"].endswith("讲讲你最有挑战的项目")
    llm = MagicMock()
    llm.generate.return_value = "建议"
    svc2 = SuggestService(llm=llm, store=store)
    assert svc2.suggest(s.session_id) == "建议"


def test_build_messages_includes_history_after_finalized():
    store = SessionStore()
    s = store.create()
    s.append_final("第一个问题")
    s.finalize_turn(suggestion="第一个建议")
    s.append_final("第二个问题")
    svc = SuggestService(llm=_fake_llm("x"), store=store)

    msgs = svc.build_messages(s)

    # system + 1条历史user + 1条历史assistant + 当前user
    assert msgs[0]["role"] == "system"
    assert msgs[1] == {"role": "user", "content": "面试官问：第一个问题"}
    assert msgs[2] == {"role": "assistant", "content": "第一个建议"}
    assert msgs[3]["role"] == "user"


def test_suggest_calls_llm_and_finalizes_turn():
    store = SessionStore()
    s = store.create()
    s.append_final("问题X")
    llm = _fake_llm("建议Y")
    svc = SuggestService(llm=llm, store=store)

    result = svc.suggest(s.session_id)

    assert result == "建议Y"
    # 轮次已结转
    assert s.current_turn_text == ""
    assert s.history_turns[-1].suggestion == "建议Y"
    assert s.history_turns[-1].question == "问题X"
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_suggest.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写实现 `app/services/suggest.py`**

```python
"""生成建议业务：组装 prompt，调 LLM，结转轮次。"""

from typing import List

from app.prompts import SYSTEM_PROMPT
from app.services.llm import LlmClient
from app.services.session import InterviewSession, SessionStore

CURRENT_TURN_PREFIX = "面试官问："


class SuggestService:
    def __init__(self, llm: LlmClient, store: SessionStore) -> None:
        self._llm = llm
        self._store = store

    def build_messages(self, session: InterviewSession) -> List[dict]:
        """组装 messages：system + 历史(多轮 user/assistant) + 当前 user。"""
        messages: List[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in session.history_turns:
            messages.append({"role": "user", "content": CURRENT_TURN_PREFIX + turn.question})
            messages.append({"role": "assistant", "content": turn.suggestion})
        messages.append(
            {"role": "user", "content": CURRENT_TURN_PREFIX + session.current_turn_text}
        )
        return messages

    def suggest(self, session_id: str) -> str:
        """生成建议并结转当前轮次。返回建议文本。"""
        session = self._store.get(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        messages = self.build_messages(session)
        suggestion = self._llm.generate(messages)
        session.finalize_turn(suggestion=suggestion)
        return suggestion
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_suggest.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/suggest.py backend/tests/test_suggest.py
git commit -m "feat(backend): suggest service - build messages, generate, finalize turn"
```

---

## Task 6: 阿里云 NLS Token Provider（TDD）

**Files:**
- Create: `backend/app/services/token_provider.py`
- Create: `backend/tests/test_token_provider.py`

**职责：** 用阿里云 AccessKey 换 NLS Token，缓存并提前刷新。

- [ ] **Step 1: 写失败测试 `tests/test_token_provider.py`**

```python
import time
from unittest.mock import patch, MagicMock

from app.services.token_provider import NlsTokenProvider


@patch("app.services.token_provider.create_token")
def test_get_token_caches_until_expiry(mock_create):
    mock_create.return_value = ("TOKEN_ABC", int(time.time()) + 3600)
    provider = NlsTokenProvider(
        access_key_id="ak", access_key_secret="sk", region="cn-shanghai"
    )
    assert provider.get_token() == "TOKEN_ABC"
    # 第二次应命中缓存，不再调 create_token
    assert provider.get_token() == "TOKEN_ABC"
    assert mock_create.call_count == 1


@patch("app.services.token_provider.create_token")
def test_get_token_refreshes_when_near_expiry(mock_create):
    # 过期时间只剩 30s（小于 60s 提前量）
    mock_create.return_value = ("TOKEN_OLD", int(time.time()) + 30)
    provider = NlsTokenProvider(
        access_key_id="ak", access_key_secret="sk", region="cn-shanghai"
    )
    provider.get_token()  # 第一次
    mock_create.return_value = ("TOKEN_NEW", int(time.time()) + 3600)
    assert provider.get_token() == "TOKEN_NEW"
    assert mock_create.call_count == 2
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_token_provider.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写实现 `app/services/token_provider.py`**

```python
"""阿里云 NLS Token 获取与刷新。

NLS 的实时识别需要一个临时 Token（通过 AccessKey 换取），有效期约一段时间。
这里做缓存，并在过期前 60s 提前刷新。
"""

import time

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest

REFRESH_AHEAD_SECONDS = 60


def create_token(access_key_id: str, access_key_secret: str, region: str) -> tuple[str, int]:
    """调用阿里云元数据接口换 NLS Token。返回 (token, expire_timestamp)。"""
    client = AcsClient(access_key_id, access_key_secret, region)
    request = CommonRequest()
    request.set_domain("nls-meta.cn-shanghai.aliyuncs.com")
    request.set_version("2019-02-28")
    request.set_action_name("CreateToken")
    request.set_method("POST")
    response = client.do_action_with_exception(request)
    import json
    data = json.loads(response)
    token = data["Token"]["Id"]
    expire = data["Token"]["ExpireTime"]
    return token, expire


class NlsTokenProvider:
    def __init__(self, access_key_id: str, access_key_secret: str, region: str) -> None:
        self._ak = access_key_id
        self._sk = access_key_secret
        self._region = region
        self._token: str | None = None
        self._expire_at: float = 0.0

    def get_token(self) -> str:
        now = time.time()
        if self._token is None or now >= self._expire_at - REFRESH_AHEAD_SECONDS:
            self._token, expire = create_token(self._ak, self._sk, self._region)
            self._expire_at = float(expire)
        return self._token
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_token_provider.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/token_provider.py backend/tests/test_token_provider.py
git commit -m "feat(backend): aliyun nls token provider with refresh-ahead cache"
```

---

## Task 7: 阿里云 NLS 客户端封装（TDD）

**Files:**
- Create: `backend/app/services/nls_client.py`
- Create: `backend/tests/test_nls_client.py`

**职责：** 封装阿里云 NLS 实时识别的会话生命周期：启动、喂 PCM、回调 `partial`/`final`、停止。把 SDK 的回调解耦成可注入的回调函数，便于测试和路由层使用。

- [ ] **Step 1: 写失败测试 `tests/test_nls_client.py`**

```python
from unittest.mock import MagicMock, patch

from app.services.nls_client import NlsAsrSession


def test_on_sentence_begin_calls_partial_with_empty():
    # SentenceBegin 时应给一个 partial("") 以初始化当前句子
    cb = MagicMock()
    session = NlsAsrSession(
        on_partial=cb.on_partial,
        on_final=cb.on_final,
        app_key="ak",
        token="T",
    )
    msg = '{"header":{"name":"SentenceBegin","status":20000000},'
    msg += '"payload":{"index":0}}'
    session._handle_message(msg)
    cb.on_partial.assert_called_once_with("")


def test_on_transcription_result_changed_calls_partial_with_text():
    cb = MagicMock()
    session = NlsAsrSession(
        on_partial=cb.on_partial,
        on_final=cb.on_final,
        app_key="ak",
        token="T",
    )
    msg = '{"header":{"name":"TranscriptionResultChanged","status":20000000},'
    msg += '"payload":{"result":"你好"}}'
    session._handle_message(msg)
    cb.on_partial.assert_called_with("你好")


def test_on_sentence_end_calls_final_with_text():
    cb = MagicMock()
    session = NlsAsrSession(
        on_partial=cb.on_partial,
        on_final=cb.on_final,
        app_key="ak",
        token="T",
    )
    msg = '{"header":{"name":"SentenceEnd","status":20000000},'
    msg += '"payload":{"result":"你好世界"}}'
    session._handle_message(msg)
    cb.on_final.assert_called_once_with("你好世界")
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_nls_client.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: 写实现 `app/services/nls_client.py`**

```python
"""阿里云 NLS 实时语音识别会话封装。

把 NLS SDK 的回调式 API 解耦成 on_partial / on_final 两个回调，
方便上层（路由层）处理和测试。
"""

import json
from typing import Callable

import nls


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
        self._nls: nls.NlsClient | None = None

    def _handle_message(self, message: str) -> None:
        """解析 NLS 返回的 JSON 消息，分发到 partial/final 回调。

        抽成独立方法便于单测（不依赖真实 SDK 连接）。
        """
        data = json.loads(message)
        name = data["header"]["name"]
        payload = data.get("payload", {})
        if name == "SentenceBegin":
            self._on_partial("")
        elif name == "TranscriptionResultChanged":
            self._on_partial(payload.get("result", ""))
        elif name == "SentenceEnd":
            self._on_final(payload.get("result", ""))

    def start(self, on_close: Callable[[], None] | None = None) -> None:
        """建立 NLS 连接并开始转写。"""

        def _cb(result, *args):
            # nls SDK 把 JSON 字符串传给回调
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
            self._nls.stop()
            self._nls = None
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_nls_client.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/nls_client.py backend/tests/test_nls_client.py
git commit -m "feat(backend): aliyun nls asr session wrapper with partial/final callbacks"
```

---

## Task 8: 依赖注入装配

**Files:**
- Create: `backend/app/deps.py`
- Modify: `backend/app/main.py`

**职责：** 把 Settings / SessionStore / LlmClient / TokenProvider / SuggestService 单例化，供路由层注入。

- [ ] **Step 1: 写 `app/deps.py`**

```python
"""依赖注入：全局单例服务。

用 lru_cache 保证进程内单例。测试时可覆盖。
"""

from functools import lru_cache

from fastapi import Depends

from app.config import Settings, get_settings
from app.services.llm import LlmClient
from app.services.session import SessionStore
from app.services.suggest import SuggestService
from app.services.token_provider import NlsTokenProvider


@lru_cache
def get_session_store() -> SessionStore:
    return SessionStore()


@lru_cache
def get_llm(settings: Settings = Depends(get_settings)) -> LlmClient:
    return LlmClient(api_key=settings.zhipu_api_key, model=settings.zhipu_model)


@lru_cache
def get_token_provider(
    settings: Settings = Depends(get_settings),
) -> NlsTokenProvider:
    return NlsTokenProvider(
        access_key_id=settings.aliyun_access_key_id,
        access_key_secret=settings.aliyun_access_key_secret,
        region=settings.aliyun_nls_region,
    )


@lru_cache
def get_suggest_service(
    settings: Settings = Depends(get_settings),
    store: SessionStore = Depends(get_session_store),
) -> SuggestService:
    llm = get_llm(settings)
    return SuggestService(llm=llm, store=store)
```

- [ ] **Step 2: 修改 `app/main.py`，挂载路由占位（路由文件下个 task 创建）**

把 `app/main.py` 替换为：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import audio, chat

app = FastAPI(title="Interview Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(audio.router)
app.include_router(chat.router)
```

- [ ] **Step 3: 写占位 `app/routes/__init__.py`（空）和路由骨架（下一 task 实现），先建空文件让 import 不报错**

Create `backend/app/routes/__init__.py`:
```python
```

Create `backend/app/routes/audio.py`:
```python
from fastapi import APIRouter

router = APIRouter()
```

Create `backend/app/routes/chat.py`:
```python
from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 4: 冒烟验证应用能起来**

Run: `cd backend && python -c "from app.main import app; print('ok', [r.path for r in app.routes])"`
Expected: 打印 `ok ['/health', ...]`

- [ ] **Step 5: Commit**

```bash
git add backend/app/deps.py backend/app/main.py backend/app/routes/
git commit -m "feat(backend): dependency injection wiring"
```

---

## Task 9: 字幕与音频 WebSocket 路由（TDD）

**Files:**
- Modify: `backend/app/routes/audio.py`
- Create: `backend/tests/test_audio_route.py`

**职责：** `/ws/audio` WebSocket：前端连上时创建/取回 session、建立 NLS 会话；收音频帧 → 重采样 → 喂 NLS；NLS 回 partial/final → 推回前端 JSON + 把 final 追加到 session。

**消息协议：**
- 前端 → 后端：第一帧发文本 `{"type":"start","session_id":"<id>"}`（可选，无则新建）；之后发二进制音频帧。
- 后端 → 前端：`{"type":"partial","text":"..."}` / `{"type":"final","text":"...","session_id":"..."}`。

- [ ] **Step 1: 写失败测试 `tests/test_audio_route.py`**

```python
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.deps import get_session_store, get_token_provider
from app.services.session import SessionStore


def _override_deps(monkeypatch_session_store=None, nls_factory=None):
    store = monkeypatch_session_store or SessionStore()
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_token_provider] = lambda: MagicMock()
    return store


def test_audio_ws_creates_session_and_streams_final():
    store = _override_deps()

    # 用 fake NlsSession：start 时立即触发一次 final 回调
    fake_nls_instances = []

    class FakeNls:
        def __init__(self, on_partial, on_final, app_key, token):
            self.on_final = on_final
            fake_nls_instances.append(self)

        def start(self, **_):
            self.on_final("你好面试官")

        def send_audio(self, _):
            pass

        def stop(self):
            pass

    client = TestClient(app)

    with patch("app.routes.audio.NlsAsrSession", FakeNls):
        with client.websocket_connect("/ws/audio") as ws:
            # 收到第一条 final 消息
            msg = json.loads(ws.receive_text())
            assert msg["type"] == "final"
            assert msg["text"] == "你好面试官"
            assert "session_id" in msg
            sid = msg["session_id"]
            # final 应已累积到 session
            assert store.get(sid).current_turn_text == "你好面试官"

    app.dependency_overrides.clear()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_audio_route.py -v`
Expected: FAIL（路由还没实现 / NlsAsrSession 未导入）

- [ ] **Step 3: 写实现 `app/routes/audio.py`**

```python
"""音频 + 字幕 WebSocket 路由。

协议：
- 前端首帧（文本）: {"type":"start","session_id":"<可选>"}
- 前端后续帧: 二进制音频（48k float32 pcm）
- 后端 -> 前端: {"type":"partial","text":"..."} | {"type":"final","text":"...","session_id":"..."}
"""

import json

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.deps import get_session_store, get_token_provider
from app.services.nls_client import NlsAsrSession
from app.services.resampler import resample_to_16k_s16
from app.services.session import SessionStore
from app.config import Settings, get_settings

router = APIRouter()


@router.websocket("/ws/audio")
async def audio_ws(
    websocket: WebSocket,
    settings: Settings = Depends(get_settings),
    store: SessionStore = Depends(get_session_store),
    token_provider=Depends(get_token_provider),
) -> None:
    await websocket.accept()
    session = None
    nls_session: NlsAsrSession | None = None

    async def _send_json(payload: dict) -> None:
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    try:
        while True:
            msg = await websocket.receive()
            if "text" in msg:
                data = json.loads(msg["text"])
                if data.get("type") == "start":
                    sid = data.get("session_id")
                    session = store.get_or_create(sid) if sid else store.create()
                    token = token_provider.get_token()
                    nls_session = NlsAsrSession(
                        on_partial=lambda t: _send_partial_sync(t, websocket, session),
                        on_final=lambda t: _handle_final(t, session, store, websocket),
                        app_key=settings.aliyun_nls_app_key,
                        token=token,
                    )
                    nls_session.start()
                    await _send_json({"type": "ready", "session_id": session.session_id})
            elif "bytes" in msg:
                if nls_session is None:
                    continue
                pcm16 = resample_to_16k_s16(msg["bytes"], in_rate=settings.input_sample_rate)
                nls_session.send_pcm(pcm16)
    except WebSocketDisconnect:
        pass
    finally:
        if nls_session is not None:
            nls_session.stop()


def _handle_final(text: str, session, store: SessionStore, websocket: WebSocket) -> None:
    """NLS final 回调（同步上下文里被 SDK 调用）。"""
    if session is None:
        return
    session.append_final(text)
    payload = {"type": "final", "text": text, "session_id": session.session_id}
    # 注意：SDK 回调在独立线程，websocket.send_text 是协程，不能直接 await。
    # 这里用同步发送（Starlette 在另一线程里调度）。
    import asyncio
    asyncio.run_coroutine_threadsafe(
        websocket.send_text(json.dumps(payload, ensure_ascii=False)),
        loop=asyncio.get_event_loop(),
    )


def _send_partial_sync(text: str, websocket: WebSocket, session) -> None:
    payload = {"type": "partial", "text": text}
    import asyncio
    asyncio.run_coroutine_threadsafe(
        websocket.send_text(json.dumps(payload, ensure_ascii=False)),
        loop=asyncio.get_event_loop(),
    )
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_audio_route.py -v`
Expected: PASS (1 passed)

  > **注意：** NLS SDK 回调在子线程，`_handle_final`/`_send_partial_sync` 用 `asyncio.run_coroutine_threadsafe` 把发送调度回事件循环。测试里用 FakeNls 在 start 时同步触发，能覆盖累积逻辑。

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/audio.py backend/tests/test_audio_route.py
git commit -m "feat(backend): audio + subtitle websocket route with nls wiring"
```

---

## Task 10: 生成建议与追问路由（TDD）

**Files:**
- Modify: `backend/app/routes/chat.py`
- Create: `backend/tests/test_chat_route.py`

**职责：**
- `POST /api/suggest`：同步生成建议，返回 `{session_id, suggestion, question}`。
- `GET /api/ask` (SSE)：流式追问，逐 token 推送。
- `POST /api/clear`：清空历史轮次。

- [ ] **Step 1: 写失败测试 `tests/test_chat_route.py`**

```python
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.deps import get_session_store, get_llm, get_suggest_service
from app.services.session import SessionStore
from app.services.suggest import SuggestService


def _setup_session_with_turn():
    store = SessionStore()
    s = store.create()
    s.append_final("讲讲项目")
    app.dependency_overrides[get_session_store] = lambda: store
    return store, s


def test_suggest_endpoint_returns_suggestion():
    store, s = _setup_session_with_turn()
    fake_llm = MagicMock()
    fake_llm.generate.return_value = "用 STAR 回答"
    svc = SuggestService(llm=fake_llm, store=store)
    app.dependency_overrides[get_suggest_service] = lambda: svc

    client = TestClient(app)
    resp = client.post("/api/suggest", json={"session_id": s.session_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["suggestion"] == "用 STAR 回答"
    assert body["question"] == "讲讲项目"
    # 轮次已结转
    assert s.current_turn_text == ""
    app.dependency_overrides.clear()


def test_clear_endpoint_clears_history():
    store, s = _setup_session_with_turn()
    s.finalize_turn(suggestion="a")
    s.append_final("当前")
    app.dependency_overrides[get_session_store] = lambda: store

    client = TestClient(app)
    resp = client.post("/api/clear", json={"session_id": s.session_id})
    assert resp.status_code == 200
    assert s.history_turns == []
    assert s.current_turn_text == "当前"
    app.dependency_overrides.clear()


def test_ask_endpoint_streams_chunks():
    store, s = _setup_session_with_turn()
    s.finalize_turn(suggestion="原始建议")
    fake_llm = MagicMock()
    fake_llm.stream.return_value = iter(["你", "好"])
    app.dependency_overrides[get_session_store] = lambda: store
    app.dependency_overrides[get_llm] = lambda: fake_llm

    client = TestClient(app)
    with client.stream(
        "GET", "/api/ask", params={"session_id": s.session_id, "message": "再详细"}
    ) as resp:
        chunks = []
        for line in resp.iter_lines():
            if line.startswith("data: "):
                chunks.append(json.loads(line[6:])["delta"])
    assert "".join(chunks) == "你好"
    app.dependency_overrides.clear()
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `pytest tests/test_chat_route.py -v`
Expected: FAIL（路由未实现）

- [ ] **Step 3: 写实现 `app/routes/chat.py`**

```python
"""生成建议（同步）+ 追问（SSE 流式）+ 清空历史 路由。"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.deps import get_llm, get_session_store, get_suggest_service
from app.prompts import SYSTEM_PROMPT
from app.schemas import AskRequest, SuggestRequest, SuggestResponse
from app.services.llm import LlmClient
from app.services.session import SessionStore
from app.services.suggest import CURRENT_TURN_PREFIX, SuggestService

router = APIRouter(prefix="/api")


@router.post("/suggest", response_model=SuggestResponse)
def suggest_endpoint(
    req: SuggestRequest,
    svc: SuggestService = Depends(get_suggest_service),
) -> SuggestResponse:
    session = svc._store.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    question_snapshot = session.current_turn_text
    suggestion = svc.suggest(req.session_id)
    return SuggestResponse(
        session_id=req.session_id,
        suggestion=suggestion,
        question=question_snapshot,
    )


@router.post("/clear")
def clear_endpoint(
    req: SuggestRequest,
    store: SessionStore = Depends(get_session_store),
) -> dict:
    session = store.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    session.clear_history()
    return {"session_id": req.session_id, "cleared": True}


@router.get("/ask")
def ask_endpoint(
    session_id: str,
    message: str,
    store: SessionStore = Depends(get_session_store),
    llm: LlmClient = Depends(get_llm),
) -> StreamingResponse:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")

    # 组装追问的 messages：system + 历史轮次 + 上一轮建议 + 用户追问
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for turn in session.history_turns:
        messages.append({"role": "user", "content": CURRENT_TURN_PREFIX + turn.question})
        messages.append({"role": "assistant", "content": turn.suggestion})
    messages.append({"role": "user", "content": message})

    async def event_stream():
        for delta in llm.stream(messages):
            payload = json.dumps({"delta": delta}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `pytest tests/test_chat_route.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/chat.py backend/tests/test_chat_route.py
git commit -m "feat(backend): suggest (sync), ask (SSE), clear routes"
```

---

## Task 11: 后端整体冒烟 + 文档

**Files:**
- Create: `backend/README.md`
- Create: `docs/SETUP.md`（BlackHole 配置）

- [ ] **Step 1: 跑全部测试**

Run: `cd backend && pytest -v`
Expected: 全部 PASS

- [ ] **Step 2: 写 `backend/README.md`**

```markdown
# 面试助手 后端

## 安装
cd backend
pip install -e ".[dev]"
cp .env.example .env  # 填入阿里云 / 智谱 key

## 运行
uvicorn app.main:app --reload --port 8000

## 测试
pytest -v
```

- [ ] **Step 3: 写 `docs/SETUP.md`（BlackHole 部分）**

```markdown
# 环境配置（macOS）

## 1. 安装 BlackHole 2ch（虚拟声卡）
- 下载: https://existential.audio/blackhole/
- 安装后重启系统

## 2. 设置多输出设备（同时听到 + 虚拟捕获）
- 打开"音频 MIDI 设置"
- 左下角 "+" → "创建多输出设备"
- 勾选: BlackHole 2ch + 你的扬声器/耳机
- 主时钟设为扬声器

## 3. 设置输入设备
- 系统设置 → 声音 → 输入 → 选择 BlackHole 2ch

## 4. 浏览器授权
- 打开前端页面
- 浏览器会请求麦克风权限
- 在弹窗的设备列表里选 BlackHole 2ch

## 5. 启动腾讯会议
- 在腾讯会议设置里，扬声器选"多输出设备"
- 这样会议声音会同时进入 BlackHole，前端能采到

## 验证
前端字幕区应随面试官说话实时出现文字。
```

- [ ] **Step 4: Commit**

```bash
git add backend/README.md docs/SETUP.md
git commit -m "docs: backend readme and blackhole setup"
```

---

## Task 12: 前端项目骨架

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/types.ts`

- [ ] **Step 1: 初始化项目**

Run:
```bash
cd /Users/shifen/ZCodeProject
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
```

- [ ] **Step 2: 配置 `vite.config.ts`（含 dev 代理）**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
```

- [ ] **Step 3: 写 `src/types.ts`**

```typescript
export interface SubtitleLine {
  text: string;
  isFinal: boolean;
}

export interface SuggestResult {
  sessionId: string;
  suggestion: string;
  question: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}
```

- [ ] **Step 4: 写最小 `src/App.tsx`（占位，后续 task 填充）**

```tsx
function App() {
  return <div>面试助手（骨架）</div>
}
export default App
```

- [ ] **Step 5: 验证能启动**

Run: `cd frontend && npm run dev`（后台跑），访问 `http://localhost:5173` 能看到页面。
Expected: 页面显示"面试助手（骨架）"

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): vite react-ts skeleton with proxy"
```

---

## Task 13: 音频采集 Hook（AudioWorklet）

**Files:**
- Create: `frontend/src/audio/capture-worklet.ts`
- Create: `frontend/src/hooks/useAudioCapture.ts`

**职责：** `getUserMedia` 拿到流（用户选 BlackHole），用 AudioWorklet 每 ~100ms 取一帧 Float32PCM，通过回调输出字节。

- [ ] **Step 1: 写 `src/audio/capture-worklet.ts`**

```typescript
// AudioWorkletProcessor: 每 N 帧把 PCM postMessage 出去
class CaptureProcessor extends AudioWorkletProcessor {
  private buffer: Float32Array[] = []
  private readonly framesPerChunk = 4800  // 100ms @ 48kHz

  process(inputs: Float32[][][]) {
    const input = inputs[0]
    if (input && input[0]) {
      this.buffer.push(input[0].slice())
      const total = this.buffer.reduce((s, b) => s + b.length, 0)
      if (total >= this.framesPerChunk) {
        const merged = new Float32Array(this.framesPerChunk)
        let offset = 0
        while (offset < this.framesPerChunk && this.buffer.length) {
          const chunk = this.buffer[0]
          const need = this.framesPerChunk - offset
          if (chunk.length <= need) {
            merged.set(chunk, offset)
            offset += chunk.length
            this.buffer.shift()
          } else {
            merged.set(chunk.subarray(0, need), offset)
            this.buffer[0] = chunk.subarray(need)
            offset += need
          }
        }
        // 转 float32 字节
        const bytes = new Uint8Array(merged.buffer.slice(0))
        this.port.postMessage(bytes.buffer, [bytes.buffer])
      }
    }
    return true
  }
}

registerProcessor('capture-processor', CaptureProcessor)
```

- [ ] **Step 2: 写 `src/hooks/useAudioCapture.ts`**

```typescript
import { useCallback, useRef, useState } from 'react'

export function useAudioCapture(onChunk: (pcmBytes: ArrayBuffer) => void) {
  const [isCapturing, setIsCapturing] = useState(false)
  const ctxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const nodeRef = useRef<AudioWorkletNode | null>(null)

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
    })
    streamRef.current = stream
    const ctx = new AudioContext({ sampleRate: 48000 })
    ctxRef.current = ctx
    await ctx.audioWorklet.addModule(
      new URL('../audio/capture-worklet.ts', import.meta.url)
    )
    const source = ctx.createMediaStreamSource(stream)
    const node = new AudioWorkletNode(ctx, 'capture-processor')
    node.port.onmessage = (e) => onChunk(e.data as ArrayBuffer)
    source.connect(node)
    // 不连到 destination（不回放）
    setIsCapturing(true)
  }, [onChunk])

  const stop = useCallback(() => {
    nodeRef.current?.disconnect()
    streamRef.current?.getTracks().forEach((t) => t.stop())
    ctxRef.current?.close()
    nodeRef.current = null
    streamRef.current = null
    ctxRef.current = null
    setIsCapturing(false)
  }, [])

  return { isCapturing, start, stop }
}
```

- [ ] **Step 3: 冒烟（手动）**：在 App 里临时调 `useAudioCapture`，打开页面授权后看控制台无报错。
（自动化验证留到集成 task。）

- [ ] **Step 4: Commit**

```bash
git add frontend/src/audio/ frontend/src/hooks/useAudioCapture.ts
git commit -m "feat(frontend): audio capture via getUserMedia + audioworklet"
```

---

## Task 14: 字幕 WebSocket Hook + 字幕面板

**Files:**
- Create: `frontend/src/api/asrSocket.ts`
- Create: `frontend/src/hooks/useSubtitle.ts`
- Create: `frontend/src/components/SubtitlePanel.tsx`

**职责：** 连 `/ws/audio`，发 start，收 partial/final，维护字幕列表（当前句缓冲 + 历史定稿）。

- [ ] **Step 1: 写 `src/api/asrSocket.ts`**

```typescript
import { useCallback, useRef } from 'react'

export interface AsrCallbacks {
  onPartial: (text: string) => void
  onFinal: (text: string, sessionId: string) => void
  onReady: (sessionId: string) => void
}

export function useAsrSocket(cb: AsrCallbacks) {
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    const ws = new WebSocket('ws://localhost:8000/ws/audio')
    ws.binaryType = 'arraybuffer'
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start' }))
    }
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'ready') cb.onReady(msg.session_id)
      else if (msg.type === 'partial') cb.onPartial(msg.text)
      else if (msg.type === 'final') cb.onFinal(msg.text, msg.session_id)
    }
    wsRef.current = ws
  }, [cb])

  const sendAudio = useCallback((buf: ArrayBuffer) => {
    wsRef.current?.send(buf)
  }, [])

  const close = useCallback(() => {
    wsRef.current?.close()
    wsRef.current = null
  }, [])

  return { connect, sendAudio, close }
}
```

- [ ] **Step 2: 写 `src/hooks/useSubtitle.ts`**

```typescript
import { useCallback, useRef, useState } from 'react'
import { useAsrSocket } from '../api/asrSocket'
import type { SubtitleLine } from '../types'

export function useSubtitle() {
  const [lines, setLines] = useState<SubtitleLine[]>([])
  const [currentPartial, setCurrentPartial] = useState('')
  const [sessionId, setSessionId] = useState('')
  const linesRef = useRef<SubtitleLine[]>([])

  const cb = {
    onReady: (sid: string) => setSessionId(sid),
    onPartial: (text: string) => setCurrentPartial(text),
    onFinal: (text: string, _sid: string) => {
      setCurrentPartial('')
      setLines((prev) => {
        const next = [...prev, { text, isFinal: true }]
        linesRef.current = next
        return next
      })
    },
  }
  const asr = useAsrSocket(cb)
  return { lines, currentPartial, sessionId, ...asr }
}
```

- [ ] **Step 3: 写 `src/components/SubtitlePanel.tsx`**

```tsx
import type { SubtitleLine } from '../types'

interface Props {
  lines: SubtitleLine[]
  currentPartial: string
}

export function SubtitlePanel({ lines, currentPartial }: Props) {
  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 12 }}>
      {lines.map((l, i) => (
        <p key={i} style={{ margin: '4px 0' }}>{l.text}</p>
      ))}
      {currentPartial && (
        <p style={{ color: '#999', margin: '4px 0' }}>
          {currentPartial} <span>（识别中）</span>
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/asrSocket.ts frontend/src/hooks/useSubtitle.ts frontend/src/components/SubtitlePanel.tsx
git commit -m "feat(frontend): subtitle websocket hook + panel"
```

---

## Task 15: 生成建议 + 追问 SSE Hook 与面板

**Files:**
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/hooks/useChat.ts`
- Create: `frontend/src/components/SuggestPanel.tsx`

- [ ] **Step 1: 写 `src/api/chat.ts`**

```typescript
import type { SuggestResult } from '../types'

const BASE = 'http://localhost:8000/api'

export async function postSuggest(sessionId: string): Promise<SuggestResult> {
  const resp = await fetch(`${BASE}/suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!resp.ok) throw new Error(`suggest failed: ${resp.status}`)
  return resp.json()
}

export async function postClear(sessionId: string): Promise<void> {
  await fetch(`${BASE}/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
}

export async function* streamAsk(
  sessionId: string,
  message: string
): AsyncGenerator<string> {
  const resp = await fetch(
    `${BASE}/ask?session_id=${encodeURIComponent(sessionId)}&message=${encodeURIComponent(message)}`
  )
  if (!resp.ok) throw new Error(`ask failed: ${resp.status}`)
  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const payload = JSON.parse(line.slice(6))
        if (payload.delta) yield payload.delta
      }
    }
  }
}
```

- [ ] **Step 2: 写 `src/hooks/useChat.ts`**

```typescript
import { useCallback, useState } from 'react'
import { postSuggest, postClear, streamAsk } from '../api/chat'
import type { ChatMessage, SuggestResult } from '../types'

export function useChat(sessionId: string) {
  const [suggestion, setSuggestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState('')
  const [followups, setFollowups] = useState<ChatMessage[]>([])

  const generate = useCallback(async () => {
    setLoading(true)
    setSuggestion('')
    try {
      const res: SuggestResult = await postSuggest(sessionId)
      setSuggestion(res.suggestion)
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  const ask = useCallback(async (message: string) => {
    setFollowups((p) => [...p, { role: 'user', content: message }])
    setStreaming('')
    let acc = ''
    for await (const delta of streamAsk(sessionId, message)) {
      acc += delta
      setStreaming(acc)
    }
    setFollowups((p) => [...p, { role: 'assistant', content: acc }])
    setStreaming('')
  }, [sessionId])

  const clear = useCallback(async () => {
    await postClear(sessionId)
    setSuggestion('')
    setFollowups([])
  }, [sessionId])

  return { suggestion, loading, streaming, followups, generate, ask, clear }
}
```

- [ ] **Step 3: 写 `src/components/SuggestPanel.tsx`**

```tsx
import { useState } from 'react'
import type { ChatMessage } from '../types'

interface Props {
  suggestion: string
  loading: boolean
  streaming: string
  followups: ChatMessage[]
  onAsk: (msg: string) => void
}

export function SuggestPanel({ suggestion, loading, streaming, followups, onAsk }: Props) {
  const [input, setInput] = useState('')
  const send = () => {
    if (input.trim()) {
      onAsk(input.trim())
      setInput('')
    }
  }

  return (
    <div style={{ height: '100%', padding: 12, display: 'flex', flexDirection: 'column' }}>
      <h3>回答建议</h3>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading ? (
          <p>生成中...</p>
        ) : (
          <p style={{ whiteSpace: 'pre-wrap' }}>{suggestion}</p>
        )}
        {streaming && <p style={{ color: '#666', whiteSpace: 'pre-wrap' }}>{streaming}</p>}
        <hr />
        {followups.map((m, i) => (
          <p key={i} style={{ textAlign: m.role === 'user' ? 'right' : 'left' }}>
            <strong>{m.role === 'user' ? '你' : '助手'}：</strong>{m.content}
          </p>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="追问..."
          style={{ flex: 1 }}
        />
        <button onClick={send}>发送</button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/chat.ts frontend/src/hooks/useChat.ts frontend/src/components/SuggestPanel.tsx
git commit -m "feat(frontend): suggest + ask SSE hooks and panel"
```

---

## Task 16: 主界面组装与控制按钮

**Files:**
- Create: `frontend/src/components/Controls.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 写 `src/components/Controls.tsx`**

```tsx
interface Props {
  isCapturing: boolean
  onStart: () => void
  onStop: () => void
  onSuggest: () => void
  onClear: () => void
}

export function Controls({ isCapturing, onStart, onStop, onSuggest, onClear }: Props) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: 12, borderBottom: '1px solid #ddd' }}>
      {isCapturing ? (
        <button onClick={onStop}>⏹ 停止采集</button>
      ) : (
        <button onClick={onStart}>▶ 开始采集</button>
      )}
      <button onClick={onSuggest}>生成建议</button>
      <button onClick={onClear}>清空上下文</button>
    </div>
  )
}
```

- [ ] **Step 2: 组装 `src/App.tsx`**

```tsx
import { useCallback } from 'react'
import { Controls } from './components/Controls'
import { SubtitlePanel } from './components/SubtitlePanel'
import { SuggestPanel } from './components/SuggestPanel'
import { useAudioCapture } from './hooks/useAudioCapture'
import { useChat } from './hooks/useChat'
import { useSubtitle } from './hooks/useSubtitle'

function App() {
  const subtitle = useSubtitle()
  const chat = useChat(subtitle.sessionId)

  const handleChunk = useCallback(
    (buf: ArrayBuffer) => subtitle.sendAudio(buf),
    [subtitle]
  )
  const { isCapturing, start, stop } = useAudioCapture(handleChunk)

  const onStart = async () => {
    subtitle.connect()
    await start()
  }
  const onStop = () => {
    stop()
    subtitle.close()
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Controls
        isCapturing={isCapturing}
        onStart={onStart}
        onStop={onStop}
        onSuggest={chat.generate}
        onClear={chat.clear}
      />
      <div style={{ flex: 1, display: 'flex' }}>
        <div style={{ flex: 1, borderRight: '1px solid #ddd' }}>
          <SubtitlePanel lines={subtitle.lines} currentPartial={subtitle.currentPartial} />
        </div>
        <div style={{ flex: 1 }}>
          <SuggestPanel
            suggestion={chat.suggestion}
            loading={chat.loading}
            streaming={chat.streaming}
            followups={chat.followups}
            onAsk={chat.ask}
          />
        </div>
      </div>
    </div>
  )
}

export default App
```

- [ ] **Step 3: 启动前后端联调（手动验证清单）**

Run（三个终端）:
```bash
# 终端1
cd backend && uvicorn app.main:app --reload --port 8000
# 终端2
cd frontend && npm run dev
```

验证清单：
- [ ] 访问 `http://localhost:5173`，看到左右分栏界面
- [ ] 点"开始采集"，浏览器弹出麦克风权限，选 BlackHole
- [ ] 播放一段音频，左侧字幕区出现文字（先灰后黑）
- [ ] 点"生成建议"，右侧出现 GLM 回答建议
- [ ] 在追问框输入文字发送，流式显示回复
- [ ] 点"清空上下文"，历史与建议清空

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Controls.tsx frontend/src/App.tsx
git commit -m "feat(frontend): main layout assembly with controls"
```

---

## Task 17: 错误处理与边界打磨

**Files:**
- Modify: `backend/app/routes/audio.py`（NLS 异常处理）
- Modify: `backend/app/routes/chat.py`（LLM 异常 → 500 友好消息）
- Modify: `frontend/src/App.tsx`（连接失败提示）
- Modify: `frontend/src/hooks/useChat.ts`（生成失败提示）

- [ ] **Step 1: 后端 audio 路由加 try/except 包住 NLS 调用**

在 `app/routes/audio.py` 的 `audio_ws` 里，把建立 NLS 会话那段包进 try/except，失败时给前端发 `{"type":"error","message":"..."}` 并关闭。

```python
# 在 start 分支里，nls_session.start() 处
try:
    nls_session.start()
    await _send_json({"type": "ready", "session_id": session.session_id})
except Exception as e:
    await _send_json({"type": "error", "message": f"ASR 启动失败: {e}"})
    await websocket.close()
    return
```

- [ ] **Step 2: 后端 chat 路由的 suggest 加异常**

```python
# suggest_endpoint 里调用 svc.suggest 处
try:
    suggestion = svc.suggest(req.session_id)
except Exception as e:
    raise HTTPException(status_code=500, detail=f"生成失败: {e}")
```

- [ ] **Step 3: 前端 `useChat.ts` 的 generate 加 try/except + 错误状态**

```typescript
const [error, setError] = useState('')
const generate = useCallback(async () => {
  setLoading(true); setError(''); setSuggestion('')
  try {
    const res = await postSuggest(sessionId)
    setSuggestion(res.suggestion)
  } catch (e) {
    setError(`生成失败：${(e as Error).message}`)
  } finally {
    setLoading(false)
  }
}, [sessionId])
```

在返回对象里加 `error`。

- [ ] **Step 4: 跑全部后端测试确认无回归**

Run: `cd backend && pytest -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/ frontend/src/
git commit -m "feat: error handling for ASR/LLM failures with user-facing messages"
```

---

## Self-Review 已完成

对 spec 各节点的覆盖核对：
- ✅ 音频采集（前端 getUserMedia）→ Task 13
- ✅ 重采样（后端）→ Task 2
- ✅ 阿里云 NLS（Token + 会话 + 桥接）→ Task 6, 7, 9
- ✅ 字幕显示（含中间结果）→ Task 14
- ✅ 手动按按钮切问题轮次 → Task 15（generate）+ Task 16（按钮）
- ✅ 智谱 GLM 同步生成 + 流式追问 → Task 4, 5, 10
- ✅ System prompt（面试教练，无简历，闲聊判断）→ Task 4
- ✅ 历史轮次 + 清空 → Task 3, 10
- ✅ 状态存内存 → Task 3
- ✅ 错误处理 → Task 17
- ✅ BlackHole 配置文档 → Task 11

类型/签名一致性已核对：`suggest()`、`finalize_turn()`、`append_final()`、`build_messages()`、`CURRENT_TURN_PREFIX` 等跨任务命名一致。无占位符。
