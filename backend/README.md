# 面试助手 后端

把会议里面试官的话实时转写成文本，按按钮后用智谱 GLM 生成回答建议，并可追问。
配合 `frontend/` 前端使用。支持 macOS（BlackHole）与 Windows（Voicemeeter），详见 `../docs/SETUP.md`。

## 安装

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # 填入阿里云 / 智谱的 key
```

## 必需的凭据

| 变量 | 说明 |
|------|------|
| `ALIYUN_ACCESS_KEY_ID` / `ALIYUN_ACCESS_KEY_SECRET` | 阿里云主账号 RAM 密钥（需开通"智能语音交互 NLS"） |
| `ALIYUN_NLS_APP_KEY` | NLS 项目的 AppKey（在 NLS 控制台创建实时语音识别项目后获得） |
| `ALIYUN_NLS_REGION` | 默认 `cn-shanghai`，NLS 实时识别目前仅上海可用 |
| `ZHIPU_API_KEY` | 智谱开放平台 API Key |
| `ZHIPU_MODEL` | 默认 `glm-4-plus`，可改为 `glm-4-flash` 等 |

## 运行

```bash
. .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

健康检查：`curl http://localhost:8000/health` → `{"status":"ok"}`

## 测试

```bash
pytest -v
```

## API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| WS | `/ws/audio` | 前端发音频帧 + start 指令；后端回 ready/partial/final 字幕 |
| POST | `/api/suggest` | 用当前轮次文本生成回答建议（同步） |
| POST | `/api/clear` | 清空历史轮次 |
| GET | `/api/ask` | SSE 流式追问 `?session_id=&message=` |

## 架构

```
浏览器音频(48k float32) ──WS──▶ routes/audio.py
                                  │ resampler 48k→16k s16
                                  ▼
                          services/nls_client.py ──WS──▶ 阿里云 NLS
                                  │ partial/final
                                  ▼
                            services/session.py (内存累积)
                                  │ 按"生成建议"
                                  ▼
                          services/suggest.py + services/llm.py ──▶ 智谱 GLM
```
