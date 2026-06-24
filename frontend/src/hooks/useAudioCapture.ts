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
