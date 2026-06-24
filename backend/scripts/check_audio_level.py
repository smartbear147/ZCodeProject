"""快速诊断：抓默认音频输入，算音量电平。

用法：python scripts/check_audio_level.py
然后播放有声音的视频，看打印的 RMS 电平是不是变化。

- 如果电平一直是 0 或恒定不变 -> 抓到的是静音（BlackHole 没声音流过）
- 如果电平随声音忽大忽小 -> 音频正常，问题在别处
"""

import array
import time

try:
    import sounddevice as sd
    HAVE_SD = True
except ImportError:
    HAVE_SD = False


def main() -> None:
    if not HAVE_SD:
        # 没装 sounddevice，用最小依赖的 wave + pyaudio 也行，但这里直接提示
        print("需要 sounddevice: pip install sounddevice numpy")
        print("（numpy 已经装了）")
        return

    print("正在抓取默认音频输入 8 秒...")
    print("请现在播放一段有声音的视频，观察电平变化：\n")

    import numpy as np

    duration = 8
    fs = 48000
    # 录 8 秒
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1, dtype="float32")
    for i in range(duration):
        time.sleep(1)
        # 实时算已录部分的 RMS
        so_far = recording[: (i + 1) * fs]
        rms = float(np.sqrt(np.mean(so_far**2)))
        bar = "#" * int(rms * 200)
        print(f"  第 {i+1}s  RMS={rms:.5f}  {bar}")
    sd.wait()

    rms = float(np.sqrt(np.mean(recording**2)))
    peak = float(np.max(np.abs(recording)))
    print(f"\n总计: RMS={rms:.5f}  峰值={peak:.5f}")
    if rms < 0.001:
        print("\n❌ 电平太低（接近静音）。抓到的不是真实声音。")
        print("   -> 问题在 BlackHole：系统声音没流过它。需要配『多输出设备』。")
    else:
        print("\n✅ 检测到有效音频电平。音频采集本身没问题。")


if __name__ == "__main__":
    main()
