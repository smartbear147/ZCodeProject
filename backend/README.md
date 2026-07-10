# 面试助手 后端

实时转写面试官的系统音频，用 LLM 生成可直接念出的回答建议，支持追问、多会话、文档管理。
配合 `frontend/` 前端使用。支持 macOS（BlackHole）与 Windows（Voicemeeter），详见 `../docs/SETUP.md`。

## 安装

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # 填入阿里云 + LLM 的 key
```

## 必需的凭据

| 变量 | 说明 |
|------|------|
| `ALIYUN_ACCESS_KEY_ID` / `ALIYUN_ACCESS_KEY_SECRET` | 阿里云主账号 RAM 密钥（需开通"智能语音交互 NLS"） |
| `ALIYUN_NLS_APP_KEY` | NLS 项目的 AppKey（在 NLS 控制台创建实时语音识别项目后获得） |
| `ALIYUN_NLS_REGION` | 默认 `cn-shanghai`，NLS 实时识别目前仅上海可用 |
| `LLM_API_KEY` | LLM API Key（智谱/DeepSeek/小米 MiMo/Ollama 等） |
| `LLM_BASE_URL` | OpenAI 兼容接口地址，默认 `https://open.bigmodel.cn/api/paas/v4` |
| `LLM_MODEL` | 模型名，默认 `glm-4-plus`，可改为 `deepseek-chat`、`mimo-pro` 等 |

## 运行

```bash
. .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

健康检查：`curl http://localhost:8000/health` → `{"status":"ok"}`

## 测试

```bash
pytest -v
pytest tests/test_session.py -v
pytest tests/test_session.py::test_name -v
```

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

## 架构

```
浏览器音频(48k float32) ──WS──▶ routes/audio.py
                                  │ resampler 48k→16k s16
                                  ▼
                          services/nls_client.py ──WS──▶ 阿里云 NLS
                                  │ partial/final
                                  ▼
                          services/session.py (字幕暂存区 subtitle_lines)
                                  │ 点击"发送字幕"
                                  ▼
                  services/chat_service.py + services/llm.py ──▶ LLM
                                  │ 流式 SSE
                                  ▼
                          浏览器 ChatPanel（对话历史）

文档管理：
  /api/documents/* ──▶ routes/documents.py → doc_parser.py → document_store.py
                                                         │ 生成回答时注入 system prompt
                                                         ▼
                                           chat_service.py → build_system_prompt_with_docs()
```

## 数据持久化

- 会话：`data/sessions.json`（含对话历史 + 字幕暂存区，重启不丢）
- 文档：`data/documents.json`（简历/题库全文，重启不丢）
- 两者均用原子写（先写 `.tmp` 再 rename），避免并发写损坏