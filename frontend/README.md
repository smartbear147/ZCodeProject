# 面试助手 前端

React + Vite + TypeScript 单页应用：左侧实时字幕 + 右侧对话，支持多会话切换和文档管理。

## 安装运行

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173`。

> 首次运行需先启动后端（见 `backend/README.md`），前端通过 Vite 代理 `/api`、`/ws` 到 `http://localhost:8000`。

## 使用流程

1. 按 [docs/SETUP.md](../docs/SETUP.md) 配好虚拟声卡（macOS：BlackHole；Windows：Voicemeeter）
2. 启动后端 + 前端
3. 进入腾讯会议（扬声器选"多输出设备"）
4. 在前端点 **▶ 开始采集**，在顶部「输入设备」下拉框选你的虚拟声卡（macOS：BlackHole 2ch；Windows：VoiceMeeter Output）
5. 面试官提问时，左侧实时显示字幕
6. 问题问完后点 **发送字幕**，右侧出现可直接念出的回答
7. 可在右侧对话框继续追问（流式回复）
8. 想重置对话点 **重置对话**，清空字幕点 **清空字幕**
9. 点 **📁 管理** 上传简历和题库，让回答更贴近真实经历
10. 左侧会话列表可新建/切换/删除会话，重启后历史不丢

## 目录结构

```
src/
├── App.tsx                     # 路由壳：/ → InterviewPage，/manage → ManagePage
├── routes/
│   ├── InterviewPage.tsx       # 面试助手页：字幕 + 对话 + 会话侧边栏
│   └── ManagePage.tsx          # 文档管理页：上传简历/题库 + 文档列表
├── components/
│   ├── Controls.tsx            # 顶部控制栏（采集按钮、设备选择、音量条、管理入口）
│   ├── SubtitlePanel.tsx       # 字幕区（实时识别 + 手动删行/清空 + 发送字幕）
│   ├── ChatPanel.tsx           # 对话区（流式回复 + 手动输入 + 重置对话）
│   ├── SessionSidebar.tsx      # 会话列表侧边栏（新建/切换/删除/收起）
│   ├── DocumentUpload.tsx      # 文档上传（文件选择 + 类型单选 + 上传按钮）
│   └── DocumentList.tsx        # 文档列表（名称/类型/大小/删除）
├── hooks/
│   ├── useAudioCapture.ts      # getUserMedia + AudioWorklet 采集 + 实时音量
│   ├── useSubtitle.ts          # 字幕状态（ASR WebSocket + 删行/清空/发送）
│   ├── useChat.ts              # 对话状态（流式发送 + 切换会话恢复历史）
│   ├── useSessions.ts          # 会话管理（列表/新建/切换/删除 + localStorage 恢复）
│   ├── useDevices.ts           # 音频输入设备枚举 + devicechange 监听
│   └── useDocuments.ts         # 文档管理（列表/上传/删除）
├── api/
│   ├── asrSocket.ts            # /ws/audio WebSocket 客户端
│   ├── chat.ts                 # /api/chat, /api/session/* 对话 + 会话 API
│   └── documents.ts            # /api/documents/* 文档 API
├── audio/
│   └── capture-worklet.ts      # AudioWorkletProcessor（~100ms float32 PCM）
└── types.ts                    # SubtitleLine, ChatMessage, DocumentInfo
```

## 关键设计

- **会话切换**：`useSessions` 管理会话列表和当前 sessionId（从 localStorage 恢复），`useChat` 和 `useSubtitle` 监听 sessionId 变化各自从后端加载历史。
- **字幕与对话解耦**：字幕区（`subtitle_lines`）是识别结果暂存区，可手动编辑；对话区（`messages`）是发给 LLM 的完整历史。两者通过"发送字幕"按钮桥接。
- **AudioWorklet 必须连 destination**：`useAudioCapture.ts` 用 gain=0 的 GainNode 接 `ctx.destination`，保证 `process()` 持续运行，同时不回放声音。