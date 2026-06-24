# 面试助手 - Windows 支持设计文档

**日期**: 2026-06-24
**状态**: 待实现

## 背景

当前应用代码本身已是跨平台的（前端用标准 Web API `getUserMedia` + AudioWorklet，后端为 Python/FastAPI），唯一与平台相关的是**系统音频路由方案**：`docs/SETUP.md` 仅描述了 macOS 下用 BlackHole 虚拟声卡 + 音频 MIDI 设置的"多输出设备"。全仓 grep `mac / darwin / blackhole / platform` 仅命中两处，均为注释/字体栈，不构成逻辑依赖。

本设计在**不重构采集架构**的前提下，让程序在 Windows 上可用。

## 目标

- Windows 用户可使用本程序，体验与 macOS 版对称。
- 减少因"抓到真实麦克风（自己的声音）而非面试官系统音频"导致的排障成本。
- 保留 macOS 支持（双平台并存）。

## 平台策略：双平台并存

代码无需按平台分支。`SETUP.md` 拆为「macOS（BlackHole）」「Windows（Voicemeeter）」两节；注释与 README 同时提及两个平台。

## 方案总览（三大改动）

1. **前端**：新增音频输入设备下拉框 + 实时音量条。
2. **Windows 文档**：`SETUP.md` 新增 Voicemeeter 配置节。
3. **措辞清理**：README、注释、`CLAUDE.md` 去掉 macOS 专属限定。

## 前端模块设计

### 设备枚举与选择
- 用 `enumerateDevices()` 过滤 `audioinput`，填充顶部下拉框。
- 选中的 `deviceId` 以 `audio: { deviceId: { exact: id } }` 传给 `getUserMedia`。
- **权限顺序**：浏览器要求先授权才显示设备真名（label）。首次"开始采集"先走一次 `getUserMedia`（触发系统授权弹窗、选 Voicemeeter），授权后下拉框才填充真名，之后可随时切换设备并重连。

### 实时音量条
- 在音频图上从 `source` 再分一支接 `AnalyserNode`（只读分析，不影响采集 worklet）。
- 主线程用 `requestAnimationFrame` 读 `getByteTimeDomainData` 算 RMS，映射为 0–100 的条。
- 抓错设备（抓到自己麦克风）时无波形或波形与环境不符，一眼可识别。

### 音频图
```
source → worklet(capture) → silentGain(gain=0) → destination   （现有，不变）
source → analyser                                          （新增，仅分析）
```

### 交互
- `Controls` 顶部新增「音频输入设备」下拉框 + 音量条；未授权/未选时显示占位。
- 现有开始/停止/生成建议/清空逻辑不变。

## 后端

**无逻辑改动。** `resampler` / `nls_client` / `session` / `llm` / `token_provider` 均平台无关。

## 文档改动清单

| 文件 | 改动 |
|------|------|
| `docs/SETUP.md` | 新增「Windows（Voicemeeter）」节（安装→系统默认播放设为 Voicemeeter Input→硬件输出指扬声器→腾讯会议扬声器选 Voicemeeter Input→浏览器授权+下拉框选 Voicemeeter Out→验证）；保留 macOS 节 |
| `backend/README.md`、`frontend/README.md` | 平台措辞由"macOS"改为"macOS/Windows"，点向 SETUP.md 对应节 |
| `frontend/src/hooks/useAudioCapture.ts` | 注释 BlackHole → "BlackHole（macOS）/ Voicemeeter（Windows）" |
| `CLAUDE.md` | 项目简介更新为双平台；补充设备选择+音量条的前端约定 |

## 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 架构路线 | 对称方案（保留 getUserMedia + 虚拟声卡） | 不重构后端，改动最小，体验与 macOS 一致 |
| Windows 路由 | Voicemeeter | 无监听延迟，对应 macOS"多输出设备"，体验最佳 |
| 前端交互 | 设备下拉框 + 实时音量条 | 减少"抓错麦克风"困惑，调试直观 |
| 音量实现 | AnalyserNode | 独立于采集 worklet，不污染采集逻辑 |
| 平台策略 | 双平台并存 | 代码本就跨平台，无需砍掉 macOS |

## 验证

- 前端 `npm run build`（`tsc -b`）类型检查通过。
- 后端 `pytest -v` 全绿（本次不改后端逻辑，应无回归）。
- 手动验证（Windows）：Voicemeeter 配好后——音量条有波形、字幕在 1–2s 内出现、扬声器监听无延迟。

## 非目标

- 不改后端采集 / ASR / LLM 逻辑。
- 不引入后端原生系统音频捕获（WASAPI loopback）。
- 不为设备选择做自动化测试（浏览器音频权限难以自动化）。
