import { useCallback, useRef, useState } from 'react'

/**
 * 采集系统音频（用户在授权弹窗里选 BlackHole 虚拟声卡），
 * 用 AudioWorklet 每 ~100ms 取一帧 float32 PCM，通过 onChunk 回调输出。
 */
export function useAudioCapture(onChunk: (pcmBytes: ArrayBuffer) => void) {
  const [isCapturing, setIsCapturing] = useState(false)
  const [error, setError] = useState('')
  const ctxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const nodeRef = useRef<AudioWorkletNode | null>(null)
  const onChunkRef = useRef(onChunk)
  onChunkRef.current = onChunk

  const start = useCallback(async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      })
      streamRef.current = stream
      const ctx = new AudioContext({ sampleRate: 48000 })
      ctxRef.current = ctx
      await ctx.audioWorklet.addModule(
        new URL('../audio/capture-worklet.ts', import.meta.url),
      )
      const source = ctx.createMediaStreamSource(stream)
      const node = new AudioWorkletNode(ctx, 'capture-processor')
      node.port.onmessage = (e: MessageEvent) => {
        onChunkRef.current(e.data as ArrayBuffer)
      }
      source.connect(node)
      nodeRef.current = node
      // 故意不连到 destination：不把音频回放出去
      setIsCapturing(true)
    } catch (e) {
      setError(`音频采集失败：${(e as Error).message}`)
    }
  }, [])

  const stop = useCallback(() => {
    nodeRef.current?.disconnect()
    streamRef.current?.getTracks().forEach((t) => t.stop())
    ctxRef.current?.close().catch(() => {})
    nodeRef.current = null
    streamRef.current = null
    ctxRef.current = null
    setIsCapturing(false)
  }, [])

  return { isCapturing, error, start, stop }
}
