# 面试助手 前端

React + Vite + TypeScript 单页应用：左侧实时字幕，右侧回答建议 + 追问。

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
6. 面试官问完后点 **✨ 生成建议**，右侧出现回答思路
7. 在右侧追问框继续提问（流式回复）
8. 想重新开始就点 **🗑 清空上下文**

## 目录结构

```
src/
├── App.tsx                  # 主界面：左右分栏 + 控制栏
├── api/
│   ├── asrSocket.ts         # /ws/audio WebSocket 客户端
│   └── chat.ts              # /api/suggest /clear /ask(SSE)
├── hooks/
│   ├── useAudioCapture.ts   # getUserMedia + AudioWorklet 采集
│   ├── useSubtitle.ts       # 字幕状态
│   └── useChat.ts           # 建议 + 追问状态
├── components/
│   ├── Controls.tsx         # 顶部按钮
│   ├── SubtitlePanel.tsx    # 左侧字幕
│   └── SuggestPanel.tsx     # 右侧建议 + 追问
├── audio/
│   └── capture-worklet.ts   # AudioWorkletProcessor
└── types.ts
```
