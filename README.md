# 面试助手

配合腾讯会议使用的面试辅助 Web 应用：实时捕获系统音频转写字幕，一键生成"可直接念出来"的回答建议，并支持追问优化。

## 功能

- **实时音频捕获**：浏览器 `getUserMedia` + AudioWorklet 采集系统音频（需虚拟声卡）
- **实时语音转写**：阿里云 NLS 流式识别，支持 partial/final 结果
- **智能回答**：基于简历和题库生成第一人称、可直接复述的完整答案
- **流式对话**：支持继续追问获得更详细建议
- **多会话管理**：像 ChatGPT 的侧边栏，支持新建/切换/删除会话，对话历史重启不丢
- **文档管理**：上传 PDF 简历和 Markdown 面试题库，回答时自动参考真实经历
- **多 LLM 支持**：智谱 GLM、DeepSeek、小米 MiMo、本地 Ollama 等任意 OpenAI 兼容 API

## 快速开始

### 1. 配置 `.env`

```bash
cd backend
cp .env.example .env
```

编辑 `.env` 填入密钥：
```ini
# 阿里云 NLS（语音识别）
ALIYUN_ACCESS_KEY_ID=你的AccessKey ID
ALIYUN_ACCESS_KEY_SECRET=你的AccessKey Secret
ALIYUN_NLS_APP_KEY=你的NLS AppKey
ALIYUN_NLS_REGION=cn-shanghai

# LLM（OpenAI 兼容接口，可切换任意服务商）
LLM_API_KEY=你的API Key
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_MODEL=glm-4-plus
```

### 2. 安装虚拟声卡

- **Windows**：[Voicemeeter](https://vb-audio.com/Voicemeeter/)，安装后重启电脑，系统播放设备设为 "VoiceMeeter Input"，Voicemeeter HARDWARE OUT A1 选扬声器/耳机
- **macOS**：[BlackHole](https://existential.audio/blackhole/)，安装后创建"多输出设备"（BlackHole + 扬声器）

### 3. 一键启动

配好 `.env` 和虚拟声卡后，首次运行会自动建 venv 和安装依赖：

- **Windows**：双击 `start.bat`
- **macOS / Linux / Git Bash**：`bash start.sh`

后端 :8000，前端 :5173。打开浏览器访问 http://localhost:5173。

### 4. 手动启动

```bash
# 后端
cd backend
python -m venv .venv && .venv\Scripts\activate   # macOS: . .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000

# 前端（另一个终端）
cd frontend
npm install
npm run dev
```

### 5. 使用

1. 打开 http://localhost:5173，点 **▶ 开始采集**
2. 在顶部「输入设备」下拉框选虚拟声卡（Windows: VoiceMeeter Output / macOS: BlackHole 2ch）
3. 面试官说话时，左侧实时显示字幕
4. 点 **发送字幕**，右侧出现可直接念出的回答
5. 可在右侧对话框继续追问
6. 点 **📁 管理** 上传简历和题库，让回答更贴近真实经历
7. 左侧会话列表可新建/切换/删除会话，重启后历史不丢

## 项目结构

```
backend/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # pydantic-settings 配置
│   ├── deps.py              # 依赖注入
│   ├── prompts.py           # System prompt（含简历/题库拼装）
│   ├── schemas.py           # Pydantic 数据模型
│   └── routes/
│       ├── audio.py         # /ws/audio 音频 WebSocket
│       ├── chat.py          # /api/chat, /api/session/* 对话 + 会话管理
│       └── documents.py     # /api/documents/* 文档管理
│   └── services/
│       ├── chat_service.py  # 对话业务（组装 prompt + 流式生成）
│       ├── document_store.py# 文档持久化
│       ├── doc_parser.py    # PDF/Markdown 解析
│       ├── llm.py           # 通用 OpenAI 兼容 LLM 客户端
│       ├── nls_client.py    # 阿里云 NLS ASR
│       ├── resampler.py     # 48k→16k 重采样（numpy）
│       ├── session.py       # 会话状态管理 + JSON 持久化
│       └── token_provider.py# NLS Token 获取与刷新
├── data/                    # 运行时数据（sessions.json, documents.json）
├── scripts/
│   └── check_audio_level.py # 虚拟声卡诊断工具
└── tests/

frontend/
├── src/
│   ├── routes/
│   │   ├── InterviewPage.tsx # 面试助手页（字幕 + 对话）
│   │   └── ManagePage.tsx   # 文档管理页（上传简历/题库）
│   ├── components/
│   │   ├── Controls.tsx     # 顶部控制栏（采集/设备/音量/管理入口）
│   │   ├── SubtitlePanel.tsx# 字幕区（实时识别 + 手动编辑）
│   │   ├── ChatPanel.tsx    # 对话区（流式回复）
│   │   ├── SessionSidebar.tsx# 会话列表侧边栏
│   │   ├── DocumentUpload.tsx# 文档上传组件
│   │   └── DocumentList.tsx # 文档列表组件
│   ├── hooks/               # 自定义 hooks
│   ├── api/                 # 后端 API 客户端
│   ├── audio/               # AudioWorklet 采集处理器
│   └── types.ts
```

## 故障排除

**没有字幕**：检查音量条是否跳动（没跳动说明没抓到声音）→ 确认虚拟声卡配置正确 → 确认 `.env` 密钥正确

**音量条有波形但没字幕**：检查阿里云 NLS AppKey 是否开通"实时语音识别"、区域是否选"上海"

**生成回答失败**：检查 LLM API Key、`LLM_BASE_URL`、`LLM_MODEL` 配置

**后端启动报错**：确认 Python ≥ 3.11，`.env` 存在且密钥正确

**前端打不开**：确认两个终端都在运行，http://localhost:8000/health 返回 `{"status":"ok"}`

**音频诊断**：`python backend/scripts/check_audio_level.py` — 录制默认输入 8 秒并打印 RMS 电平

## 环境要求

- Python ≥ 3.11
- Node.js（前端构建）
- 阿里云账号（NLS 语音识别）
- 任意 OpenAI 兼容 LLM 服务
- 虚拟声卡（Windows: Voicemeeter / macOS: BlackHole）

## License

MIT