# 面试助手 - 设计文档

**日期**: 2026-06-23
**状态**: 待审核

## 一句话概述

一个 Web 应用，配合腾讯会议使用。求职者在面试时，系统实时把面试官的话转成文本，求职者按一下按钮，智谱 GLM 基于这段问题生成"回答建议"，并可继续追问。

## 背景与目标

- **场景**: 求职者通过腾讯会议参加面试。
- **用户角色**: 求职者（本系统的使用者）。
- **核心价值**: 帮求职者听清面试官的完整问题，并快速获得回答思路，提升面试表现。
- **音频来源**: 腾讯会议里面试官的声音，通过 macOS 系统音频捕获（虚拟声卡，如 BlackHole）。
- **语音识别**: 阿里云 NLS 实时流式识别（WebSocket）。
- **大模型**: 智谱 GLM。

## 核心交互流程

```
进入面试模式
    │
    ▼
持续转写面试官的话 ──▶ 实时字幕滚动（含中间结果）
    │
    │ 面试官问完一个问题
    ▼
按"生成建议"按钮
    │
    ▼
把从上次按按钮以来的所有定稿字幕 → 作为本轮问题 → 发给 GLM
    │
    ▼
GLM 生成"回答建议"卡片（含：考察点、回答方向、示范开头）
    │
    ▼
可追问（流式返回）："再详细点" "换个角度" 等
    │
    │ 下一轮面试官提问
    ▼
再按一次"生成建议" → 开始新一轮（清空当前轮次文本）
```

## 整体架构

```
┌─────────────────────────────────────────────────────┐
│  浏览器 (前端 React + Vite)                          │
│  - getUserMedia 采集系统音频（选中 BlackHole 虚拟声卡）│
│  - 字幕区（中间结果 + 定稿）                          │
│  - 生成建议按钮 / 追问输入框 / 清空上下文             │
└───────────────┬─────────────────────────────────────┘
                │ WebSocket (音频流上行 / 字幕下行)
                │ SSE (追问 GLM 流式回复)
┌───────────────▼─────────────────────────────────────┐
│  后端 (Python + FastAPI)                             │
│  1. 音频接收 ← 前端 WebSocket                        │
│  2. 重采样 48k Float32 → 16k 16-bit PCM             │
│  3. ASR 桥接 → 阿里云 NLS WebSocket                  │
│  4. 会话状态管理（当前轮次 / 历史轮次）               │
│  5. LLM 调用 → 智谱 GLM（同步生成 / 流式追问）       │
└─────────────────────────────────────────────────────┘
```

## 模块设计

### 目录结构

```
project/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 阿里云/智谱 key、模型参数
│   ├── routes/
│   │   ├── audio.py         # WebSocket: 接收前端音频流 + 推送字幕
│   │   └── chat.py          # SSE: 追问流式接口；REST: 生成建议
│   ├── services/
│   │   ├── asr.py           # 阿里云 NLS WebSocket 桥接
│   │   ├── llm.py           # 智谱 GLM 调用（同步 + 流式）
│   │   ├── session.py       # 会话状态管理
│   │   └── suggest.py       # 生成建议业务逻辑：组装 prompt
│   ├── audio/
│   │   └── resample.py      # 48k→16k 重采样
│   └── prompts.py           # System prompt 模板
├── frontend/                # React + Vite
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── SubtitlePanel.tsx     # 字幕区
│   │   │   ├── SuggestPanel.tsx      # 建议区 + 追问
│   │   │   └── Controls.tsx          # 按钮（开始/生成建议/清空）
│   │   └── hooks/
│   │       ├── useAudioCapture.ts    # getUserMedia + 音频帧采集
│   │       ├── useAsrSocket.ts       # 字幕 WebSocket
│   │       └── useChat.ts            # SSE 追问
│   └── ...
└── docs/superpowers/specs/
```

### 前端模块

#### `useAudioCapture`
- 调用 `getUserMedia({ audio: true })`，用户在浏览器权限弹窗里选 BlackHole 作为麦克风源。
- 用 `AudioWorklet`（或兼容的 `ScriptProcessorNode`）每 ~100ms 抓一帧 Float32 PCM（48kHz）。
- 通过 WebSocket 把音频帧二进制发送给后端。

#### `useAsrSocket`
- 维护到后端的 WebSocket 连接（与音频上行共用，或分离）。
- 接收两类字幕消息：
  - `partial`（中间结果）：更新当前句子缓冲，浅色 + "(识别中)" 显示。
  - `final`（SentenceEnd 定稿）：把当前句子加到字幕历史，清空缓冲。
- 把定稿字幕同步给后端的 session（后端累积到 `current_turn_text`）。

#### `SubtitlePanel`（字幕区）
- 滚动显示，最新在底部。
- 当前识别中的句子：浅灰色 + "(识别中)" 后缀。
- 定稿句子：正常颜色。

#### `SuggestPanel`（建议区 + 追问）
- 显示 GLM 生成的"回答建议"。
- 生成中显示 "生成中..."。
- 追问输入框 + 发送按钮。
- 追问回复流式显示（SSE）。
- 历史追问记录在下方折叠区。

#### `Controls`（控制按钮）
- **"生成建议"**：触发后端 `/api/suggest`，用 `current_turn_text` 调 GLM，返回后清空当前轮次、存入历史。
- **"清空上下文"**：清掉 `history_turns`，让 GLM 忘掉前面问过什么。

### 后端模块

#### `routes/audio.py`（音频 + 字幕 WebSocket）
- 接收前端音频帧（二进制 Float32）。
- 转发到 `services/asr.py` 做识别。
- 把识别结果（partial/final）推回前端。

#### `services/asr.py`（阿里云 NLS 桥接）
- 启动时/过期前刷新 NLS Token。
- 为每个会话建立到阿里云 NLS 的 WebSocket。
- 发 `StartTranscription`（16k、开启标点、返回中间结果）。
- 推送重采样后的 PCM 帧。
- 解析阿里云返回的事件：
  - `SentenceBegin`
  - `TranscriptionResultChanged` → 推 `partial` 给前端
  - `SentenceEnd` → 推 `final` 给前端，并追加到 `session.current_turn_text`

#### `audio/resample.py`
- 48kHz Float32 → 16kHz 16-bit 单声道 PCM。
- 用 `audioop` 或简单线性降采样。

#### `services/session.py`（会话状态，内存）
```python
class InterviewSession:
    session_id: str
    current_turn_text: str        # 当前轮次累积的定稿字幕
    history_turns: list[dict]     # 历史轮次 [{question, suggestion}, ...]
    asr_connection: object        # 到阿里云 NLS 的 WebSocket
    is_listening: bool            # 是否在转写
```
- 一个浏览器连接 = 一个 session，用 WebSocket 连接 id 关联。
- 状态只存内存，重启丢失（本期不持久化）。

#### `services/suggest.py`（生成建议）
- 组装 System Prompt + 当前轮次问题 + 可选历史轮次。
- 调 `services/llm.py` 同步生成。
- 返回结果，更新 session（存入 `history_turns`，清空 `current_turn_text`）。

#### `routes/chat.py`（追问 SSE）
- 接收追问文本，组装 prompt（当前建议 + 历史 + 追问）。
- 调 `services/llm.py` 流式生成。
- 通过 SSE 推给前端。

#### `services/llm.py`（智谱 GLM）
- 用 API Key + Secret Key 鉴权（JWT）。
- 同步生成：用于"生成建议"。
- 流式生成（`stream=True`）：用于追问。

### Prompt 设计

**System Prompt（通用面试教练，无简历/JD）：**
```
你是一位资深面试教练，帮助求职者应对面试。

任务：针对面试官的问题，给出回答建议。要求：
1. 先简要点出面试官在考察什么
2. 给出 1-2 个回答方向/要点（建议用 STAR 结构：情境-任务-行动-结果）
3. 如适合，给一个简短的回答示范开头
4. 不要替求职者编造具体经历或数据，只给思路和框架

特别注意：
- 如果面试官的话只是寒暄/闲聊（如"你今天怎么样""路上堵车吗"），不要给正式回答建议，只回复"[非正式问题，闲聊即可]"。
```

**User Message（生成建议）：**
```
面试官问：[current_turn_text]
```

**User Message（追问）：**
```
[带上历史轮次 + 当前建议]
用户追问：[追问文本]
```

## 关键设计决策汇总

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 音频采集位置 | 前端 getUserMedia | macOS 系统音频捕获（BlackHole）配成虚拟麦克风，浏览器直接选，后端不碰底层设备 |
| 重采样位置 | 后端 Python | 前端 AudioWorklet 重采样调试麻烦，后端几行搞定 |
| ASR 接入 | 阿里云 NLS 实时流式 WebSocket | 实时性，边说边出字 |
| 问题切分 | 手动按"生成建议"按钮 | 面试问题跨多句，需人工判断何时问完 |
| 中间结果显示 | 显示 | 更快看到面试官在问什么 |
| LLM 用途 | 生成回答建议 + 追问 | 帮求职者快速组织回答思路 |
| 生成建议返回 | 同步 | 一次性完整结果即可 |
| 追问返回 | 流式 SSE | 等结果时体验更好 |
| 闲聊判断 | LLM 自己判断 | prompt 里指示，简化前端 |
| 简历/JD 配置 | 本期不做 | 简化，后续可加 |
| 暂停转写 | 不要 | 闲聊由 LLM 判断 |
| 历史轮次 | 默认记住，可手动清空 | 避免重复建议，又能重置 |
| 状态存储 | 内存 | 本期不持久化，简单优先 |
| 技术栈 | React + Vite / FastAPI / 智谱 SDK / 阿里云 NLS | 轻量、生态好 |

## 待办与开放问题

- macOS BlackHole 安装与配置指南（用户操作步骤，需在 README 里写清楚）。
- 浏览器对 BlackHole 作为 `getUserMedia` 输入源的兼容性实测。
- 阿里云 NLS 的具体 SDK 选型（官方 Python SDK 还是直接 WebSocket）。
- 智谱 GLM 的具体模型版本（GLM-4 / GLM-4-Plus / GLM-4-Flash 等，按成本/质量定）。

## 非目标（本期不做）

- 简历/JD 配置与个性化。
- 面试录音/纪要持久化。
- 多用户、多会话并发（本期单用户单进程）。
- 移动端适配。
- 英文面试支持（prompt 可调，但本期以中文为主）。
