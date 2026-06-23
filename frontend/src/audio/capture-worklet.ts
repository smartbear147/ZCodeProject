/// <reference lib="webworker" />

// AudioWorkletProcessor：累积 PCM 帧，每攒够约 100ms（4800 帧 @48kHz）
// 把 float32 数据 postMessage 给主线程，主线程再通过 WebSocket 发往后端。

class CaptureProcessor extends AudioWorkletProcessor {
  private buffer: Float32Array[] = []
  private readonly framesPerChunk = 4800 // ~100ms @ 48kHz

  process(inputs: Float32[][][]): boolean {
    const input = inputs[0]
    if (input && input[0] && input[0].length > 0) {
      // 拷贝一帧（AudioWorklet 的 buffer 会被复用，必须 slice）
      this.buffer.push(input[0].slice())

      const total = this.buffer.reduce((sum, b) => sum + b.length, 0)
      if (total >= this.framesPerChunk) {
        const merged = new Float32Array(this.framesPerChunk)
        let offset = 0
        while (offset < this.framesPerChunk && this.buffer.length > 0) {
          const chunk = this.buffer[0]
          const need = this.framesPerChunk - offset
          if (chunk.length <= need) {
            merged.set(chunk, offset)
            offset += chunk.length
            this.buffer.shift()
          } else {
            merged.set(chunk.subarray(0, need), offset)
            this.buffer[0] = chunk.subarray(need)
            offset += need
          }
        }
        // transferable：避免拷贝大块内存
        const copy = new Float32Array(merged)
        this.port.postMessage(copy.buffer, [copy.buffer])
      }
    }
    return true
  }
}

registerProcessor('capture-processor', CaptureProcessor)
