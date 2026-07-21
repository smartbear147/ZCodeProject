# AGENTS.md

本文件为 Codex (Codex.ai/code) 在本仓库中工作时提供指引。

## 项目简介

面试助手：一个配合腾讯会议使用的 Web 应用。它捕获面试官的系统音频，实时转写成字幕（阿里云 NLS），并在按下按钮时把累积的文本送给 LLM 生成可直接念出的回答建议，还可进行流式追问。支持上传简历和面试题库，让回答更贴近真实经历。代码与界面均为中文——请沿用该约定。

**功能：**
- 实时音频捕获：通过浏览器 `getUserMedia` + AudioWorklet 捕获系统音频（需虚拟声卡）
- 实时语音转写：阿里云 NLS 流式识别（默认），可选小米 MiMo 分块转写（`ASR_PROVIDER` 切换），均输出 partial/final 结果
- 智能回答：基于简历和题库上下文，生成第一人称、可直接复述的完整答案
- 流式对话：支持继续追问获得更详细建议
- 多会话管理：像 ChatGPT 的侧边栏，支持新建/切换/删除/重命名会话，历史重启不丢
- 文档管理：上传 PDF 简历和 Markdown 面试题库，回答时自动参考
- 多 LLM 支持：智谱 GLM、DeepSeek、小米 MiMo、本地 Ollama 等任意 OpenAI 兼容 API

**典型使用场景：**
求职者通过腾讯会议参加面试时，系统实时转写面试官的问题，一键生成回答建议，并支持追问优化。

仓库顶层有三个目录：`backend/`（Python/FastAPI）、`frontend/`（React/Vite/TS）和 `docs/`。系统音频捕获靠虚拟声卡：macOS 用 BlackHole、Windows 用 Voicemeeter，使系统音频能作为 `getUserMedia` 输入被捕获，配置见 `README.md`。前端顶部有「输入设备」下拉框（选虚拟声卡）和实时音量条（抓错设备时可一眼看出没波形）。

## 环境配置

### 必需的 API 密钥

1. **语音识别**（二选一，`ASR_PROVIDER` 切换，默认 aliyun）：
   - **阿里云 NLS**：注册阿里云账号并开通"智能语音交互"服务；在 RAM 访问控制创建 AccessKey（ID 和 Secret）；在 NLS 控制台创建"实时语音识别"项目获取 AppKey；区域选择"上海"（当前唯一可用区域）
   - **小米 MiMo ASR**：只需 `MIMO_API_KEY`（https://mimo.xiaomi.com/），OpenAI 兼容分块转写，延迟高于 NLS

2. **LLM**（大语言模型，OpenAI 兼容接口）：
   - 智谱 GLM：https://open.bigmodel.cn/
   - DeepSeek：https://platform.deepseek.com/
   - 小米 MiMo：https://mimo.xiaomi.com/
   - 本地 Ollama：http://localhost:11434
   - 任意 OpenAI 兼容 API 均可

### 配置文件设置

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 文件填入密钥：
```ini
# 语音识别引擎：aliyun（默认）/ mimo（后者只需 MIMO_API_KEY）
ASR_PROVIDER=aliyun

# 阿里云 NLS
ALIYUN_ACCESS_KEY_ID=你的AccessKey ID
ALIYUN_ACCESS_KEY_SECRET=你的AccessKey Secret
ALIYUN_NLS_APP_KEY=你的NLS AppKey
ALIYUN_NLS_REGION=cn-shanghai

# 小米 MiMo ASR（ASR_PROVIDER=mimo 时必填）
MIMO_API_KEY=你的MiMo API Key

# LLM（OpenAI 兼容接口）
LLM_API_KEY=你的API Key
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4-plus
```

### 虚拟声卡安装

**Windows (Voicemeeter)：**
1. 下载：https://vb-audio.com/Voicemeeter/
2. 安装后**必须重启电脑**
3. 系统默认播放设备设为 "VoiceMeeter Input"
4. Voicemeeter 的 HARDWARE OUT A1 选你的扬声器/耳机

**macOS (BlackHole)：**
1. 下载：https://existential.audio/blackhole/
2. 安装后重启或登出再登入
3. 音频 MIDI 设置 → 创建"多输出设备" → 勾选 BlackHole + 扬声器

## 命令

后端（`cd backend`）：
```bash
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env            # 填入阿里云 + LLM 的密钥
uvicorn app.main:app --reload --port 8000
pytest -v                       # 全部测试
pytest tests/test_session.py -v # 单个文件
pytest tests/test_session.py::test_name -v   # 单个测试
```
健康检查：`curl http://localhost:8000/health` → `{"status":"ok"}`。要求 Python ≥ 3.11。pytest 以 `asyncio_mode = "auto"` 运行。

前端（`cd frontend`）：
```bash
npm install
npm run dev        # 开发服务器在 :5173，把 /api 和 /ws 代理到 :8000
npm run build      # tsc -b && vite build（这是唯一的类型检查关卡）
```
前端没有测试或 lint 脚本；`npm run build` 是类型检查关卡（`strict`、`noUnusedLocals`、`noUnusedParameters`）。

诊断：`python backend/scripts/check_audio_level.py` —— 录制默认输入 8 秒并打印 RMS 电平，用以判断虚拟声卡是否真的有声音流过（绝大多数"没有字幕"的问题根源在此）。

## 使用流程

### 快速启动（一键脚本）

配好 `.env` 和虚拟声卡后，直接用一键脚本同时拉起前后端（首次运行会自动建 venv、装依赖）：

- **Windows**：双击 `start.bat`（或命令行执行 `start.bat`）
- **macOS / Linux / Git Bash**：`bash start.sh`

脚本会在新窗口 / 后台启动后端（:8000）和前端（:5173）。首次运行需安装依赖（pip 装阿里云 SDK 较慢），之后秒启。停止：Windows 关闭弹出的两个窗口；macOS/Linux 在终端按 `Ctrl+C`。

> 下面 1、2 步是**手动逐个启动**的方式，适合排查问题或分别查看日志；一键脚本已自动完成这些。

### 1. 启动后端
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```
保持后端运行，不要关闭终端。

### 2. 启动前端
```bash
cd frontend
npm install
npm run dev
```
保持前端运行，不要关闭终端。

### 3. 使用软件
1. 打开浏览器访问 http://localhost:5173
2. 点击 "▶ 开始采集" 按钮
3. 浏览器弹出权限时，在"输入设备"下拉框选虚拟声卡：
   - Windows：选 "VoiceMeeter Output"
   - macOS：选 "BlackHole 2ch"
4. 看音量条：面试官说话时应有绿色跳动
5. 面试官提问，左侧实时显示字幕
6. 问题问完后点 "发送字幕"，右侧出现可直接念出的回答
7. 可在右侧对话框继续追问
8. 想重置对话点 "重置对话"，清空字幕点 "清空字幕"
9. 点 "📁 管理" 上传简历和题库，让回答更贴近真实经历
10. 左侧会话列表可新建/切换/删除会话，重启后历史不丢

### 4. 停止使用
- 点 "⏹ 停止采集"
- 关闭浏览器标签页
- 在后端终端按 `Ctrl+C` 停止服务
- 在前端终端按 `Ctrl+C` 停止服务

## 架构：数据流与会话模型

```
浏览器 AudioWorklet（48k float32，~100ms 的块）
  ──WebSocket /ws/audio──▶ routes/audio.py
                              │ resample_to_16k_s16（numpy，不是 audioop）
                              ▼
              services/asr_base.py 统一接口（deps.get_asr_factory 按 ASR_PROVIDER 二选一）
                ├─ services/nls_client.py ──NLS WS──▶ 阿里云 NLS（流式）
                └─ services/mimo_asr.py ──HTTP──▶ 小米 MiMo（分块转写）
                              │ partial/final 回调
                              ▼
                        services/session.py（subtitle_lines 字幕暂存区）
                              │ 点击"发送字幕"
                              ▼
                   services/chat_service.py + services/llm.py ──▶ LLM
                              │ 流式 SSE
                              ▼
                        浏览器 ChatPanel（对话历史）

文档管理：
  /manage 页面 ──上传 PDF/MD──▶ routes/documents.py
                                   │ parse_document
                                   ▼
                              document_store.py（JSON 持久化）
                                   │ 生成回答时注入 system prompt
                                   ▼
                              chat_service.py → build_system_prompt_with_docs()
```

**会话模型是核心概念，横跨前端与后端——在改动字幕/聊天逻辑前务必先理解它。**

一个 `InterviewSession` 包含两部分：
- `messages`：发给 LLM 的对话历史（role/content），整场面试累积，不自动清。首条 user 消息自动设为会话标题。
- `subtitle_lines`：语音识别的定稿句子，独立于对话历史。用户点"发送字幕"时，`consume_subtitles()` 把字幕区全部内容打包成一条 user message 追加进 `messages`，然后清空字幕区。删字幕/清字幕不影响对话历史。

`SessionStore` 持久化到本地 JSON（`backend/data/sessions.json`），重启不丢。`DocumentStore` 同理（`backend/data/documents.json`）。前端 `useSessions` hook 管理会话列表和当前会话，从 localStorage 恢复上次会话。

LLM 配置通过 `.env` 的 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 切换任意 OpenAI 兼容服务商（智谱/DeepSeek/小米 MiMo/本地 Ollama 等），`services/llm.py` 使用 OpenAI SDK。

## 跨文件注意事项（承载关键逻辑——删除前务必理解）

- **导入 FastAPI 之前，根 logger 被强制设为 DEBUG**（`app/main.py`）。阿里云 `nls` SDK 只通过 `logging.debug` 输出内部错误，且从不调用 `on_error`——没有 DEBUG，你会看到"start() 返回 ok 但什么都没发生"。务必把这个 `basicConfig` 保留在模块顶部。
- **NLS 回调在后台线程触发，而 WebSocket 发送是协程。** `routes/audio.py` 用 `asyncio.run_coroutine_threadsafe(websocket.send_text(...), loop)` 桥接（即 `_send` 辅助函数）。任何从 NLS 回调向客户端推送的新代码都必须走这个桥。
- **AudioWorkletNode 必须最终连到 `ctx.destination`**，否则浏览器停止拉取采样（`process()` 停止）。`useAudioCapture.ts` 通过一个 gain 为 0 的 `GainNode` → destination 来保证数据流通，同时不回放声音（避免回声）。
- **重采样使用 numpy，这是有意为之。** `audioop` 在 Python 3.13+ 已被移除；`services/resampler.py` 的流程是 float32→裁剪→线性降采样→int16。无状态、逐帧处理。
- **`nls_client._handle_message` 是纯 JSON 解析**，可独立单元测试；`nls` SDK 在 `start()` 中延迟导入，使测试不依赖真实 SDK 安装。保持消息分发的可测试性。
- **`/ws/audio` 协议**：客户端第一帧是文本 `{"type":"start"}`（可选 `session_id`）；服务器*先*回复 `{"type":"ready","session_id"}` 再启动 ASR（以免 NLS 回调抢先触发）；后续客户端帧为二进制 float32 PCM。服务器推送 `ready | partial | final | error`。
- **文档注入 system prompt**：`chat_service.py` 的 `_build_system_prompt_with_docs()` 从 `DocumentStore` 取简历和题库全文，拼入 system prompt。无文档时用基础 prompt。简历用第一人称直接作答，题库遇到相似问题优先用已有答案。
- **前端会话切换**：`useSessions` 从 localStorage 恢复上次会话，切换时 `useChat` 和 `useSubtitle` 各自从后端加载该会话的历史/字幕区。三个 hook 的 `sessionId` 变化是驱动切换的核心信号。
- **字幕与对话解耦**：字幕区（`subtitle_lines`）和对话历史（`messages`）是独立概念。字幕是识别结果的暂存区，可手动编辑（删行/清空）；对话是发给 LLM 的完整历史。两者通过"发送字幕"按钮桥接。

## 后端约定

- FastAPI 的依赖注入集中在 `app/deps.py`。`SessionStore` 和 `DocumentStore` 是进程级单例（JSON 持久化——重启不丢状态）。其他服务按请求从 `Settings` 构造；测试中可通过 `app.dependency_overrides` 覆盖。`DocumentStore` 的 `path=None` 时纯内存（测试用）。
- 配置由 `.env` 经 pydantic-settings 读取（`app/config.py`，无 env 前缀）。注意热重载：修改 `.env` 需重启服务器。
- LLM 客户端（`services/llm.py`）是通用 OpenAI 兼容接口，通过 `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` 配置切换服务商。

## 故障排除

### 没有字幕出现
1. 检查后端是否在运行（看终端输出）
2. 检查音量条有没有跳动（没跳动说明没抓到声音）
3. 确认虚拟声卡配置正确：
   - Windows：腾讯会议扬声器选"VoiceMeeter Input"，浏览器选"VoiceMeeter Output"
   - macOS：腾讯会议扬声器选"多输出设备"，浏览器选"BlackHole 2ch"
4. 确认后端 `.env` 填对了所有密钥

### 后端启动报错
1. 检查 Python 版本 ≥ 3.11：`python --version`
2. 检查 `.env` 文件是否存在并填对了密钥
3. 查看后端终端的错误信息（通常会提示具体原因）

### 前端页面打不开
1. 确认两个终端都在运行
2. 检查 http://localhost:5173 是否能访问
3. 检查 http://localhost:8000/health 是否返回 `{"status":"ok"}`

### 音量条有波形但没字幕
1. 检查阿里云 NLS 密钥是否正确
2. 检查 NLS AppKey 是否开通了"实时语音识别"服务
3. 检查 NLS 区域是否选"上海"

### 生成回答失败
1. 检查 LLM API Key 是否正确
2. 检查 `LLM_BASE_URL` 和 `LLM_MODEL` 配置
3. 查看后端终端的错误信息

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| WS | `/ws/audio` | 前端发音频帧 + start 指令；后端回 ready/partial/final 字幕 |
| POST | `/api/session` | 创建新会话，返回 session_id |
| GET | `/api/sessions` | 列出所有会话摘要（按更新时间倒序） |
| GET | `/api/session/{id}` | 获取会话详情（消息历史 + 字幕区） |
| DELETE | `/api/session/{id}` | 删除会话 |
| POST | `/api/session/rename` | 重命名会话 |
| POST | `/api/chat` | 发消息给 LLM（SSE 流式）。可选手打 message 或 send_subtitles=true 把字幕打包发出 |
| POST | `/api/reset` | 清空对话历史（字幕区不动） |
| POST | `/api/subtitle/remove-line` | 删除字幕区某一行 |
| POST | `/api/subtitle/clear` | 清空字幕区（不影响对话历史） |
| POST | `/api/documents/upload` | 上传文档（PDF 简历或 Markdown 题库） |
| GET | `/api/documents/list` | 列出已上传文档 |
| DELETE | `/api/documents/{id}` | 删除文档 |
| GET | `/health` | 健康检查 `{"status":"ok"}` |