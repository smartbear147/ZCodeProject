"""音频重采样：浏览器 48kHz float32 PCM -> 16kHz s16 单声道 PCM。

用 numpy 实现（Python 3.13+ 已移除 audioop）。无状态、逐帧处理，便于流式转码。
"""

import struct

import numpy as np

_OUTPUT_RATE = 16000


def resample_to_16k_s16(pcm_in: bytes, in_rate: int = 48000) -> bytes:
    """把 float32 单声道 PCM 转成 16kHz、16-bit 单声道 PCM。

    Args:
        pcm_in: float32 LE 字节流。
        in_rate: 输入采样率（默认 48000）。

    Returns:
        16kHz、16-bit 单声道 PCM 字节。
    """
    if not pcm_in:
        return b""

    # 1. float32 字节 -> numpy float 数组
    n_samples = len(pcm_in) // 4
    floats = np.frombuffer(pcm_in, dtype="<f4").astype(np.float64)

    # 2. 裁剪到 [-1.0, 1.0]
    floats = np.clip(floats, -1.0, 1.0)

    # 3. 线性降采样到 16k：等间距重采样
    if in_rate != _OUTPUT_RATE:
        out_len = int(round(n_samples * _OUTPUT_RATE / in_rate))
        if out_len <= 0:
            return b""
        indices = np.linspace(0, n_samples - 1, out_len)
        floats = np.interp(indices, np.arange(n_samples), floats)

    # 4. 放大到 int16 并转字节
    ints = (floats * 32767.0).astype("<i2")
    return ints.tobytes()
