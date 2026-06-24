# Windows 支持 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让面试助手在 Windows 上可用（Voicemeeter 虚拟声卡 + 设备下拉框 + 实时音量条），与 macOS 版体验对称，且保留 macOS 支持。

**Architecture:** 不改采集架构。前端在现有 `getUserMedia` + AudioWorklet 基础上：(1) 新增设备枚举下拉框，把选中的 `deviceId` 以 `exact` 约束传给 `getUserMedia`；(2) 从音频图分支接 `AnalyserNode` 算实时电平驱动音量条。系统音频路由靠 Windows 上的 Voicemeeter（虚拟声卡）。后端逻辑零改动。

**Tech Stack:** React 18 + Vite + TypeScript / `enumerateDevices` + `AnalyserNode` + `requestAnimationFrame` / Python + FastAPI（不动）

---

## 项目约定（执行前必读）

- **前端无单元测试框架**（`package.json` 只有 `dev` / `build` / `preview`）。因此前端任务的验证手段是：`npm run build`（含 `tsc -b` 类型检查，`strict` + `noUnusedLocals` + `noUnusedParameters`）通过 + 本地浏览器手动验证。**不要**为本计划引入 vitest/jest——YAGNI。
- **后端无逻辑改动**：每个任务结束后跑 `pytest -v` 仅用于确认无回归。
- 所有命令在仓库根 `E:/Code/github/ZCodeProject` 下执行；前端命令需 `cd frontend`，后端命令需 `cd backend`。
- commit 沿用仓库的 conventional commits 风格（英文前缀）。

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `frontend/src/hooks/useDevices.ts` | **新建** | 枚举 `audioinput` 设备；授权后刷新；`devicechange` 自动刷新 |
| `frontend/src/hooks/useAudioCapture.ts` | 修改 | 接受 `deviceId`；接 `AnalyserNode` 输出实时 `level`；`start` 可接受 override 设备 id |
| `frontend/src/components/Controls.tsx` | 修改 | 顶部加「输入设备」下拉框 + 音量条 |
| `frontend/src/App.tsx` | 修改 | 接线：`useDevices` + `selectedDeviceId` 状态 + 传 `level`/`devices` 给 Controls；切换设备时重连 |
| `docs/SETUP.md` | 修改 | 新增「Windows（Voicemeeter）」节，保留 macOS 节 |
| `backend/README.md`、`frontend/README.md` | 修改 | 平台措辞 macOS → macOS/Windows |
| `CLAUDE.md` | 修改 | 项目简介更新为双平台；补设备选择+音量条约定 |

---

### Task 1: 新建 `useDevices` hook（设备枚举）

**Files:**
- Create: `frontend/src/hooks/useDevices.ts`

- [ ] **Step 1: 创建文件，写入完整内容**

`frontend/src/hooks/useDevices.ts`:
```ts
import { useCallback, useEffect, useState } from 'react'

export interface AudioInputDevice {
  deviceId: string
  label: string
}

/**
 * 枚举音频输入设备。
 *
 * 浏览器要求先有 getUserMedia 授权，enumerateDevices 返回的设备才带 label
 * （否则 label 为空、deviceId 为空字符串）。所以调用方需在首次 getUserMedia
 * 成功后调用 refresh() 重新拉取，下拉框才会显示真实设备名（如 Voicemeeter Out）。
 *
 * 监听 devicechange，设备插拔时自动刷新。
 */
export function useDevices() {
  const [devices, setDevices] = useState<AudioInputDevice[]>([])

  const refresh = useCallback(async () => {
    const all = await navigator.mediaDevices.enumerateDevices()
    setDevices(
      all
        .filter((d) => d.kind === 'audioinput')
        .map((d) => ({ deviceId: d.deviceId, label: d.label || '未命名设备' })),
    )
  }, [])

  useEffect(() => {
    const handler = () => {
      void refresh()
    }
    // 部分浏览器没有 addEventListener，做防御
    navigator.mediaDevices.addEventListener?.('devicechange', handler)
    return () => {
      navigator.mediaDevices.removeEventListener?.('devicechange', handler)
    }
  }, [refresh])

  return { devices, refresh }
}
```

- [ ] **Step 2: 类型检查通过**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 TS 报错（`useDevices` 尚未被引用，但导出未被使用不会触发 `noUnusedLocals`）。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useDevices.ts
git commit -m "feat(frontend): add useDevices hook for audio input enumeration"
```

---

### Task 2: 改造 `useAudioCapture`（接受 deviceId + 输出 level）

**Files:**
- Modify: `frontend/src/hooks/useAudioCapture.ts`（整文件替换）

- [ ] **Step 1: 用以下内容整体替换 `frontend/src/hooks/useAudioCapture.ts`**

```ts
import { useCallback, useRef, useState } from 'react'

/**
 * 采集系统音频：用户在授权弹窗 / 下拉框里选虚拟声卡——
 *   macOS：BlackHole；Windows：Voicemeeter 的虚拟输出（VoiceMeeter Output）。
 * 用 AudioWorklet 每 ~100ms 取一帧 float32 PCM，通过 onChunk 输出。
 * 同时用 AnalyserNode 算实时输入电平（level，0–100），供 UI 音量条显示。
 *
 * 关键：AudioWorkletNode 必须最终连到 destination，否则浏览器认为这条
 * 音频图没有消费者，会停止拉取数据（process() 不再被调用）。
 * 这里用 gain=0 的 GainNode 接到 destination：保证数据流通，但不回放声音。
 *
 * @param deviceId 指定采集设备（来自下拉框）；为空则用默认设备（首次弹系统选择窗）
 */
export function useAudioCapture(
  onChunk: (pcmBytes: ArrayBuffer) => void,
  deviceId?: string,
) {
  const [isCapturing, setIsCapturing] = useState(false)
  const [error, setError] = useState('')
  const [level, setLevel] = useState(0)
  const ctxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const nodeRef = useRef<AudioWorkletNode | null>(null)
  const analyserRef = useRef<AnalyserNode | null>(null)
  const rafRef = useRef<number | null>(null)
  const onChunkRef = useRef(onChunk)
  const deviceIdRef = useRef(deviceId)
  onChunkRef.current = onChunk
  deviceIdRef.current = deviceId

  const stop = useCallback(() => {
    if (rafRef.current != null) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    nodeRef.current?.disconnect()
    analyserRef.current?.disconnect()
    streamRef.current?.getTracks().forEach((t) => t.stop())
    ctxRef.current?.close().catch(() => {})
    nodeRef.current = null
    analyserRef.current = null
    streamRef.current = null
    ctxRef.current = null
    setLevel(0)
    setIsCapturing(false)
  }, [])

  /**
   * 开始采集。
   * @param overrideDeviceId 切换设备时显式传入新 id，绕过 setState 异步
   *   （onSelectDevice 里 setSelectedDeviceId 后立即 start，此时 ref 尚未更新）
   */
  const start = useCallback(async (overrideDeviceId?: string) => {
    setError('')
    const id = overrideDeviceId ?? deviceIdRef.current
    try {
      const constraints: MediaStreamConstraints = {
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          ...(id ? { deviceId: { exact: id } } : {}),
        },
      }
      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      streamRef.current = stream
      const ctx = new AudioContext({ sampleRate: 48000 })
      ctxRef.current = ctx
      await ctx.audioWorklet.addModule(
        new URL('../audio/capture-worklet.ts', import.meta.url),
      )
      const source = ctx.createMediaStreamSource(stream)

      // 音量分析：source 分一支接 AnalyserNode（只读，不影响采集 worklet）
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 1024
      source.connect(analyser)
      analyserRef.current = analyser
      const buf = new Uint8Array(analyser.fftSize)
      let lastUpdate = 0
      const tick = () => {
        analyser.getByteTimeDomainData(buf)
        let sum = 0
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128
          sum += v * v
        }
        const rms = Math.sqrt(sum / buf.length)
        const now = performance.now()
        // 节流到 ~80ms 一次，避免每帧触发 React 重渲染
        if (now - lastUpdate >= 80) {
          // ×300 放大，让较弱的人声也能在音量条上可见
          setLevel(Math.min(100, Math.round(rms * 300)))
          lastUpdate = now
        }
        rafRef.current = requestAnimationFrame(tick)
      }
      rafRef.current = requestAnimationFrame(tick)

      // 采集 worklet
      const node = new AudioWorkletNode(ctx, 'capture-processor')
      node.port.onmessage = (e: MessageEvent) => {
        onChunkRef.current(e.data as ArrayBuffer)
      }
      source.connect(node)
      // 静音 GainNode 接 destination：保证音频图有消费者、process() 会跑，
      // 同时不把声音回放出去（避免回声）。
      const silentGain = ctx.createGain()
      silentGain.gain.value = 0
      node.connect(silentGain)
      silentGain.connect(ctx.destination)
      nodeRef.current = node
      setIsCapturing(true)
    } catch (e) {
      setError(`音频采集失败：${(e as Error).message}`)
    }
  }, [])

  return { isCapturing, error, level, start, stop }
}
```

- [ ] **Step 2: 类型检查通过**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 TS 报错。（`App.tsx` 仍按旧签名 `useAudioCapture(handleChunk)` 解构 `start`/`stop`，新增的 `level`、可选第二参、`start` 的可选参都不破坏现有调用，类型兼容。）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useAudioCapture.ts
git commit -m "feat(frontend): support device selection and expose audio level"
```

---

### Task 3: Controls 下拉框 + 音量条，并接线 App

> 把 Controls 和 App 放在**同一任务**里一起改、一起提交：单独改 Controls 会让 `App.tsx` 按旧 Props 调用导致 `tsc` 失败，合并才能保证每次提交都构建通过。

**Files:**
- Modify: `frontend/src/components/Controls.tsx`（整文件替换）
- Modify: `frontend/src/App.tsx`（整文件替换）

- [ ] **Step 1: 用以下内容整体替换 `frontend/src/components/Controls.tsx`**

```tsx
import type { AudioInputDevice } from '../hooks/useDevices'

interface Props {
  isCapturing: boolean
  level: number
  devices: AudioInputDevice[]
  selectedDeviceId: string
  onSelectDevice: (deviceId: string) => void
  onStart: () => void
  onStop: () => void
  onSuggest: () => void
  onClear: () => void
}

export function Controls({
  isCapturing,
  level,
  devices,
  selectedDeviceId,
  onSelectDevice,
  onStart,
  onStop,
  onSuggest,
  onClear,
}: Props) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        padding: 12,
        borderBottom: '1px solid #e0e0e0',
        alignItems: 'center',
        flexWrap: 'wrap',
      }}
    >
      <strong style={{ marginRight: 'auto' }}>面试助手</strong>

      <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        输入设备
        <select
          value={selectedDeviceId}
          onChange={(e) => onSelectDevice(e.target.value)}
          style={{ maxWidth: 220 }}
          title="选择虚拟声卡：macOS 选 BlackHole；Windows 选 VoiceMeeter Output"
        >
          <option value="">（默认 / 未选择）</option>
          {devices.map((d) => (
            <option key={d.deviceId} value={d.deviceId}>
              {d.label}
            </option>
          ))}
        </select>
      </label>

      {/* 实时输入电平：宽度随 level 变化；静音灰、有声绿 */}
      <div
        title="实时输入电平（无声时检查是否抓错了真实麦克风）"
        style={{
          width: 120,
          height: 8,
          background: '#e0e0e0',
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${level}%`,
            height: '100%',
            background: level > 2 ? '#4caf50' : '#bbb',
            transition: 'width 80ms linear',
          }}
        />
      </div>

      {isCapturing ? (
        <button onClick={onStop}>⏹ 停止采集</button>
      ) : (
        <button onClick={onStart}>▶ 开始采集</button>
      )}
      <button onClick={onSuggest}>✨ 生成建议</button>
      <button onClick={onClear}>🗑 清空上下文</button>
    </div>
  )
}
```

- [ ] **Step 2: 用以下内容整体替换 `frontend/src/App.tsx`**

```tsx
import { useCallback, useState } from 'react'
import { Controls } from './components/Controls'
import { SubtitlePanel } from './components/SubtitlePanel'
import { SuggestPanel } from './components/SuggestPanel'
import { useAudioCapture } from './hooks/useAudioCapture'
import { useChat } from './hooks/useChat'
import { useDevices } from './hooks/useDevices'
import { useSubtitle } from './hooks/useSubtitle'

function App() {
  const subtitle = useSubtitle()
  const chat = useChat(subtitle.sessionId)
  const { devices, refresh: refreshDevices } = useDevices()
  const [selectedDeviceId, setSelectedDeviceId] = useState('')

  const handleChunk = useCallback(
    (buf: ArrayBuffer) => subtitle.sendAudio(buf),
    [subtitle],
  )
  const { isCapturing, level, start, stop, error: captureError } =
    useAudioCapture(handleChunk, selectedDeviceId)

  const onStart = async () => {
    subtitle.connect()
    await start()
    // 授权后刷新设备列表，让下拉框显示真实设备名（VoiceMeeter Output 等）
    refreshDevices()
  }
  const onStop = () => {
    stop()
    subtitle.close()
  }

  // 切换设备：更新选中态；若正在采集，用新设备重连（显式传 id 绕过 setState 异步）
  const onSelectDevice = useCallback(
    async (deviceId: string) => {
      setSelectedDeviceId(deviceId)
      if (isCapturing) {
        stop()
        await start(deviceId)
      }
    },
    [isCapturing, start, stop],
  )

  // 生成建议：成功后清空左侧字幕（这轮的话已送走，开始新一轮），
  // 与后端 current_turn_text 清空保持一致。失败不清空，保留字幕方便重试。
  const onSuggest = useCallback(async () => {
    const ok = await chat.generate()
    if (ok) {
      subtitle.clearLines()
    }
  }, [chat, subtitle])

  const onClear = useCallback(async () => {
    await chat.clear()
    subtitle.clearLines()
  }, [chat, subtitle])

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Controls
        isCapturing={isCapturing}
        level={level}
        devices={devices}
        selectedDeviceId={selectedDeviceId}
        onSelectDevice={onSelectDevice}
        onStart={onStart}
        onStop={onStop}
        onSuggest={onSuggest}
        onClear={onClear}
      />
      {(captureError || subtitle.error) && (
        <div style={{ padding: '6px 12px', background: '#fff3f3', color: '#c00' }}>
          {captureError || subtitle.error}
        </div>
      )}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <div
          style={{
            flex: 1,
            borderRight: '1px solid #e0e0e0',
            minHeight: 0,
          }}
        >
          <SubtitlePanel
            lines={subtitle.lines}
            currentPartial={subtitle.currentPartial}
          />
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <SuggestPanel
            suggestion={chat.suggestion}
            loading={chat.loading}
            streaming={chat.streaming}
            followups={chat.followups}
            error={chat.error}
            onAsk={chat.ask}
          />
        </div>
      </div>
    </div>
  )
}

export default App
```

- [ ] **Step 3: 类型检查通过**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 TS 报错。

- [ ] **Step 4: 手动验证（浏览器）**

启动后端与前端，在浏览器 `http://localhost:5173`：
1. 点「▶ 开始采集」，授权弹窗出现；授权后「输入设备」下拉框应填充出真实设备名。
2. 选中一个设备（虚拟声卡）时，如有声音，音量条应出现绿色跳动。
3. 切换设备，采集应自动重连（停止再开始），无报错。
4. 点「⏹ 停止采集」，音量条归零。

（无凭证时 ASR 不会出字幕，这步只验证设备/音量条 UI 与采集重连，属预期。）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Controls.tsx frontend/src/App.tsx
git commit -m "feat(frontend): add device picker and level meter, wire into App"
```

---

### Task 4: `docs/SETUP.md` 新增 Windows（Voicemeeter）节

**Files:**
- Modify: `docs/SETUP.md`（整文件替换，保留 macOS 内容、新增 Windows 节）

- [ ] **Step 1: 用以下内容整体替换 `docs/SETUP.md`**

````markdown
# 环境配置

本系统通过捕获**系统音频**来转写会议里面试官的声音。Windows 与 macOS 默认都不允许直接抓取系统输出，需要安装一个虚拟声卡作为中转。请按你的系统选择对应章节：

- [macOS（BlackHole）](#macos-blackhole)
- [Windows（Voicemeeter）](#windows-voicemeeter)

---

## macOS（BlackHole）

本系统通过捕获**系统音频**来转写腾讯会议里面试官的声音。macOS 默认不允许直接抓取系统输出，需要安装虚拟声卡 BlackHole 作为中转。

### 1. 安装 BlackHole 2ch（虚拟声卡）

- 下载：https://existential.audio/blackhole/
- 解压后运行 `BlackHole.pkg` 安装
- 安装后需要重启 Mac（或登出再登入）让系统识别新设备

### 2. 创建"多输出设备"（既能听到又能捕获）

打开 **音频 MIDI 设置**（Spotlight 搜 "Audio MIDI Setup"）：

1. 左下角 `+` → **创建多输出设备**
2. 勾选：`BlackHole 2ch` + 你的扬声器/耳机
3. 主设备（Master Clock）设为你的扬声器/耳机

这样会议声音会同时送往扬声器（你听得见）和 BlackHole（软件能抓）。

### 3. 浏览器授权（运行前端时）

1. 启动前端，访问 `http://localhost:5173`
2. 点"开始采集"，浏览器弹出麦克风权限
3. 在顶部"输入设备"下拉框里选 **BlackHole 2ch**

> 浏览器把 BlackHole 当作一个"麦克风"输入，所以 `getUserMedia` 能直接采到系统音频。

### 4. 腾讯会议设置

腾讯会议 → 设置 → 音频：
- **扬声器** 选"多输出设备"（不是默认的耳机）
- 麦克风随便（我们不抓自己的声音）

### 5. 验证

进入前端页面后点"开始采集"，让腾讯会议里有人说话，**音量条应随声音跳动**，字幕区应在 1-2 秒内出现文字。

如果没反应，依次检查：
- 音频 MIDI 设置里"多输出设备"是否包含 BlackHole
- 浏览器下拉框是否选了 BlackHole 作为输入
- 腾讯会议扬声器是否为"多输出设备"
- 后端 `.env` 里阿里云 / 智谱 key 是否填对

---

## Windows（Voicemeeter）

Voicemeeter 是免费的虚拟调音台，能把系统音频同时送到扬声器（你听得见）和虚拟录音设备（软件能抓），正好对应 macOS 的"多输出设备"，且**无监听延迟**。

### 1. 安装 Voicemeeter

- 下载：https://vb-audio.com/Voicemeeter/
- 选 **Voicemeeter**（免费版即可，不需要 Banana）
- 安装后**重启电脑**，让虚拟声卡生效

### 2. 把系统输出送到 Voicemeeter

打开 **设置 → 系统 → 声音 → 更多声音设置**（或控制面板「声音」）：

- 在「**播放**」标签里，把 **VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)** 设为默认播放设备。
  - 这样所有系统声音（含腾讯会议）都先进入 Voicemeeter。

### 3. 让声音从扬声器/耳机出来（你听得见）

打开 **Voicemeeter** 应用：

- 右上角 **HARDWARE OUT** 区，点 **A1**，选你的真实扬声器/耳机（如「扬声器 Realtek」/ 你的 USB 耳机）。
  - 现在系统声音会经 Voicemeeter 送到 A1（你听得见），**无延迟**。

### 4. 腾讯会议设置

腾讯会议 → 设置 → 音频：
- **扬声器** 选 **VoiceMeeter Input**（让会议声音进 Voicemeeter，而不是直连扬声器）。
- 麦克风随便（我们不抓自己的声音）。

> 如果第 2 步已把系统默认播放设为 VoiceMeeter Input，腾讯会议默认就会走它；这里显式选一次更保险。

### 5. 浏览器授权（运行前端时）

1. 启动前端，访问 `http://localhost:5173`
2. 点"▶ 开始采集"，浏览器弹出麦克风权限
3. 在顶部"输入设备"下拉框里选 **VoiceMeeter Output**（名称可能是 `VoiceMeeter Output (VB-Audio VoiceMeeter VAIO)` 或 `Voicemeeter Out`，**以下拉框实际显示为准**）
4. 看旁边的**音量条**：面试官说话时应有绿色波形跳动；若没反应，多半是抓到了真实麦克风而非系统音频。

> 浏览器把 Voicemeeter 的虚拟输出当作一个"麦克风"输入，所以 `getUserMedia` 能直接采到系统音频。

### 6. 验证

让会议里有人说话，**音量条应随声音跳动**，字幕区应在 1-2 秒内出现文字。

如果没反应，依次检查：
- Voicemeeter 的 A1 是否指向了你的扬声器（第 3 步）
- 系统默认播放设备是否为 VoiceMeeter Input（第 2 步）
- 浏览器下拉框是否选了 VoiceMeeter Output（第 5 步）
- 后端 `.env` 里阿里云 / 智谱 key 是否填对
````

- [ ] **Step 2: Commit**

```bash
git add docs/SETUP.md
git commit -m "docs: add Windows (Voicemeeter) setup section"
```

---

### Task 5: 措辞清理（README×2、CLAUDE.md）

**Files:**
- Modify: `backend/README.md`、`frontend/README.md`、`CLAUDE.md`

> 注：`useAudioCapture.ts` 的注释已在 Task 2 更新为「BlackHole（macOS）/ Voicemeeter（Windows）」，无需再改。

- [ ] **Step 1: 编辑 `backend/README.md` 首段**

把开头：
```
把腾讯会议里面试官的话实时转写成文本，按按钮后用智谱 GLM 生成回答建议，并可追问。
配合 `frontend/` 前端使用。
```
改为：
```
把会议里面试官的话实时转写成文本，按按钮后用智谱 GLM 生成回答建议，并可追问。
配合 `frontend/` 前端使用。支持 macOS（BlackHole）与 Windows（Voicemeeter），详见 `../docs/SETUP.md`。
```

- [ ] **Step 2: 编辑 `frontend/README.md`「使用流程」第 1、4 条**

把第 1 条：
```
1. 按 [docs/SETUP.md](../docs/SETUP.md) 配好 BlackHole 虚拟声卡
```
改为：
```
1. 按 [docs/SETUP.md](../docs/SETUP.md) 配好虚拟声卡（macOS：BlackHole；Windows：Voicemeeter）
```

把第 4 条：
```
4. 在前端点 **▶ 开始采集**，浏览器弹窗里选 **BlackHole 2ch**
```
改为：
```
4. 在前端点 **▶ 开始采集**，在顶部「输入设备」下拉框选你的虚拟声卡（macOS：BlackHole 2ch；Windows：VoiceMeeter Output）
```

- [ ] **Step 3: 编辑 `CLAUDE.md`「项目简介」段**

把：
```
仓库顶层有三个目录:`backend/`(Python/FastAPI)、`frontend/`(React/Vite/TS)和 `docs/`。`docs/SETUP.md` 记录了 macOS 下 BlackHole 虚拟声卡的配置方式,使系统音频能作为 `getUserMedia` 输入被捕获。
```
改为：
```
仓库顶层有三个目录:`backend/`(Python/FastAPI)、`frontend/`(React/Vite/TS)和 `docs/`。系统音频捕获靠虚拟声卡:macOS 用 BlackHole、Windows 用 Voicemeeter,使系统音频能作为 `getUserMedia` 输入被捕获,配置见 `docs/SETUP.md`。前端顶部有「输入设备」下拉框(选虚拟声卡)和实时音量条(抓错设备时可一眼看出没波形)。
```

- [ ] **Step 4: Commit**

```bash
git add backend/README.md frontend/README.md CLAUDE.md
git commit -m "docs: refer to both macOS and Windows in README/CLAUDE.md"
```

---

### Task 6: 全量验证

**Files:** 无（仅运行检查）

- [ ] **Step 1: 前端类型检查 + 构建**

Run: `cd frontend && npm run build`
Expected: 构建成功，无 TS 报错、无未使用变量报错。

- [ ] **Step 2: 后端无回归**

Run: `cd backend && . .venv/bin/activate && pytest -v`（Windows: `.venv\Scripts\activate && pytest -v`）
Expected: 全部测试通过（本次未改后端逻辑）。

- [ ] **Step 3: 手动验证清单（需真实凭证 + Voicemeeter 环境）**

在 Windows + Voicemeeter 环境下：
- [ ] 「输入设备」下拉框能看到 `VoiceMeeter Output` 选项
- [ ] 选中后，面试官说话时音量条有绿色跳动
- [ ] 字幕在 1–2s 内出现
- [ ] 扬声器能无延迟听到声音（Voicemeeter A1 已指扬声器）
- [ ] 「生成建议」「清空上下文」「追问」功能正常
