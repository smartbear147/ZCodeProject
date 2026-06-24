# 环境配置

本系统通过捕获**系统音频**来转写会议里面试官的声音。Windows 与 macOS 默认都不允许直接抓取系统输出，需要安装一个虚拟声卡作为中转。请按你的系统选择对应章节：

- [macOS（BlackHole）](#macos-blackhole)
- [Windows（Voicemeeter）](#windows-voicemeeter)

---

## macOS（BlackHole）

macOS 默认不允许直接抓取系统输出，需要安装虚拟声卡 BlackHole 作为中转。

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
