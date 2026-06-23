"""测试重采样：48k float32 -> 16k s16 单声道 PCM。"""

import math
import struct

from app.services.resampler import resample_to_16k_s16


def _make_float32_frames(freq_hz: float, duration_s: float, in_rate: int) -> bytes:
    """生成纯正弦波的 float32 PCM 字节（单声道）。"""
    n = int(duration_s * in_rate)
    samples = [math.sin(2 * math.pi * freq_hz * i / in_rate) for i in range(n)]
    return struct.pack("<%df" % n, *samples)


def test_resample_halves_sample_count():
    """48k -> 16k: 样本数约为输入的 1/3。"""
    pcm_in = _make_float32_frames(440.0, 0.1, 48000)  # 4800 samples
    pcm_out = resample_to_16k_s16(pcm_in, in_rate=48000)
    # s16 = 2 bytes/sample; 输出样本数应为输入的 1/3
    assert len(pcm_out) // 2 == 1600


def test_resample_output_clips_to_s16_range():
    """振幅超出 1.0 应裁剪到 int16 max。"""
    n = 480
    pcm_in = struct.pack("<" + "f" * n, *([5.0] * n))
    pcm_out = resample_to_16k_s16(pcm_in, in_rate=48000)
    first_sample = struct.unpack("<h", pcm_out[:2])[0]
    assert first_sample == 32767


def test_resample_empty_input():
    assert resample_to_16k_s16(b"", in_rate=48000) == b""


def test_resample_preserves_frequency():
    """降采样后主导频率应仍约为 440Hz（在 16k 采样率下）。

    用 FFT 找到频谱峰值所在的 bin，换算回频率。
    """
    import numpy as np

    pcm_in = _make_float32_frames(440.0, 0.5, 48000)  # 0.5s, 长 enough for FFT
    pcm_out = resample_to_16k_s16(pcm_in, in_rate=48000)
    samples = np.frombuffer(pcm_out, dtype="<i2").astype(np.float64)
    spectrum = np.abs(np.fft.rfft(samples))
    peak_bin = int(np.argmax(spectrum))
    peak_freq = peak_bin * 16000 / len(samples)
    assert 420 < peak_freq < 460
