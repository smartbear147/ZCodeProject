# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在本仓库中工作时提供指引。

## 项目简介

面试助手:一个配合腾讯会议使用的 Web 应用。它捕获面试官的系统音频,实时转写成字幕(阿里云 NLS),并在按下按钮时把累积的文本送给智谱 GLM 生成回答建议,还可进行流式追问。代码与界面均为中文——请沿用该约定。

仓库顶层有三个目录:`backend/`(Python/FastAPI)、`frontend/`(React/Vite/TS)和 `docs/`。系统音频捕获靠虚拟声卡:macOS 用 BlackHole、Windows 用 Voicemeeter,使系统音频能作为 `getUserMedia` 输入被捕获,配置见 `docs/SETUP.md`。前端顶部有「输入设备」下拉框(选虚拟声卡)和实时音量条(抓错设备时可一眼看出没波形)。

## 命令

后端(`cd backend`):
```bash
python3 -m venv .venv && . .venv/bin/activate   # Windows 下: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env            # 填入阿里云 + 智谱的密钥
uvicorn app.main:app --reload --port 8000
pytest -v                       # 全部测试
pytest tests/test_session.py -v # 单个文件
pytest tests/test_session.py::test_name -v   # 单个测试
```
健康检查:`curl http://localhost:8000/health` → `{"status":"ok"}`。要求 Python ≥ 3.11。pytest 以 `asyncio_mode = "auto"` 运行。

前端(`cd frontend`):
```bash
npm install
npm run dev        # 开发服务器在 :5173,把 /api 和 /ws 代理到 :8000
npm run build      # tsc -b && vite build(这是唯一的类型检查关卡)
```
前端没有测试或 lint 脚本;`npm run build` 是类型检查关卡(`strict`、`noUnusedLocals`、`noUnusedParameters`)。

诊断:`python backend/scripts/check_audio_level.py` —— 录制默认输入 8 秒并打印 RMS 电平,用以判断 BlackHole 是否真的有声音流过(绝大多数"没有字幕"的问题根源在此)。

## 架构:数据流与"轮次"模型

```
浏览器 AudioWorklet(48k float32,~100ms 的块)
  ──WebSocket /ws/audio──▶ routes/audio.py
                              │ resample_to_16k_s16(numpy,不是 audioop)
                              ▼
                        services/nls_client.py ──NLS WS──▶ 阿里云 NLS
                              │ partial/final 回调
                              ▼
                        services/session.py(内存)
                              │ 点击"生成建议"
                              ▼
                   services/suggest.py + services/llm.py ──▶ 智谱 GLM
```

**"轮次"模型是核心概念,横跨前端与后端——在改动字幕/聊天逻辑前务必先理解它。** 一个 `InterviewSession` 把 ASR 的 `final` 句子累积到 `current_turn_text`。点击"生成建议"(`POST /api/suggest`)会把该文本作为一道题目快照,调用 GLM,随后 `finalize_turn()` 把 `{question, suggestion}` 推入 `history_turns` 并清空 `current_turn_text`。前端与之对应:`useChat.generate()` 调用 `/suggest`,成功后 `App.tsx` 调用 `useSubtitle.clearLines()`,使左侧面板只显示*新一轮*的话(让前端视觉与后端已清空的轮次保持一致)。"清空上下文"(`/api/clear`)只重置 `history_turns`(GLM 的记忆),不影响进行中的轮次。追问(`GET /api/ask`,SSE)由 `SYSTEM_PROMPT` + 全部历史轮次 + 用户追问组装出 `messages`。

## 跨文件注意事项(承载关键逻辑——删除前务必理解)

- **导入 FastAPI 之前,根 logger 被强制设为 DEBUG**(`app/main.py`)。阿里云 `nls` SDK 只通过 `logging.debug` 输出内部错误,且从不调用 `on_error`——没有 DEBUG,你会看到"start() 返回 ok 但什么都没发生"。务必把这个 `basicConfig` 保留在模块顶部。
- **NLS 回调在后台线程触发,而 WebSocket 发送是协程。** `routes/audio.py` 用 `asyncio.run_coroutine_threadsafe(websocket.send_text(...), loop)` 桥接(即 `_send` 辅助函数)。任何从 NLS 回调向客户端推送的新代码都必须走这个桥。
- **AudioWorkletNode 必须最终连到 `ctx.destination`**,否则浏览器停止拉取采样(`process()` 停止)。`useAudioCapture.ts` 通过一个 gain 为 0 的 `GainNode` → destination 来保证数据流通,同时不回放声音(避免回声)。
- **重采样使用 numpy,这是有意为之。** `audioop` 在 Python 3.13+ 已被移除;`services/resampler.py` 的流程是 float32→裁剪→线性降采样→int16。无状态、逐帧处理。
- **`nls_client._handle_message` 是纯 JSON 解析**,可独立单元测试;`nls` SDK 在 `start()` 中延迟导入,使测试不依赖真实 SDK 安装。保持消息分发的可测试性。
- **`/ws/audio` 协议**:客户端第一帧是文本 `{"type":"start"}`(可选 `session_id`);服务器*先*回复 `{"type":"ready","session_id"}` 再启动 ASR(以免 NLS 回调抢先触发);后续客户端帧为二进制 float32 PCM。服务器推送 `ready | partial | final | error`。

## 后端约定

- FastAPI 的依赖注入集中在 `app/deps.py`。`SessionStore` 是进程级单例(纯内存,不持久化——重启即丢失状态)。其他服务按请求从 `Settings` 构造;测试中可通过 `app.dependency_overrides` 覆盖。
- 配置由 `.env` 经 pydantic-settings 读取(`app/config.py`,无 env 前缀)。注意热重载:修改 `.env` 需重启服务器。
- 设计与决策记录在 `docs/superpowers/specs/2026-06-23-interview-assistant-design.md`;任务拆解在 `docs/superpowers/plans/2026-06-23-interview-assistant.md`。
