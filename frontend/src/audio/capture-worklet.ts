// AudioWorkletProcessor：累积 PCM 帧，每攒够约 100ms（4800 帧 @48kHz）
// 把 float32 数据 postMessage 给主线程，主线程再通过 WebSocket 发往后端。
//
// 注意：这里依赖 DOM lib 里的 AudioWorkletProcessor / registerProcessor 全局，
// 不要用 /// <reference lib="webworker" />，否则这些名字找不到。

// TS 5.5 的 lib.dom.d.ts 没有声明 AudioWorklet 全局里的这几个名字，这里补一份最小声明。
declare abstract class AudioWorkletProcessor {
  readonly port: MessagePort
}

declare function registerProcessor(
  name: string,
  processorCtor: new () => AudioWorkletProcessor,
): void

class CaptureProcessor extends AudioWorkletProcessor {
  // 输入是 [输入端口][声道][采样] 的结构；单声道只取 [0]。
  private buffer: Float32Array[] = []
  private readonly framesPerChunk = 4800 // ~100ms @ 48kHz

  process(inputs: Float32Array[][]): boolean {
    const input = inputs[0]
    if (input && input[0] && input[0].length > 0) {
      // 拷贝一帧（AudioWorklet 的 buffer 会被复用，必须 slice）
      this.buffer.push(input[0].slice() as Float32Array)

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
            this.buffer[0] = chunk.subarray(need) as Float32Array
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
