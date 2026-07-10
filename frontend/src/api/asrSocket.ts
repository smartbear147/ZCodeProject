export interface AsrCallbacks {
  onPartial: (text: string) => void
  onFinal: (text: string, sessionId: string) => void
  onReady: (sessionId: string) => void
  onError?: (message: string) => void
}

/**
 * 连接后端 /ws/audio，发 start 指令，接收 ready/partial/final/error。
 */
export class AsrSocket {
  private ws: WebSocket | null = null

  constructor(private readonly cb: AsrCallbacks) {}

  /** 连接后端 /ws/audio。sessionId 非空时复用该会话（字幕进同一会话）。 */
  connect(sessionId?: string): void {
    // 用相对路径，Vite dev 代理到 ws://localhost:8000
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${proto}//${location.host}/ws/audio`)
    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      const payload: Record<string, unknown> = { type: 'start' }
      if (sessionId) payload.session_id = sessionId
      ws.send(JSON.stringify(payload))
    }
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'ready') this.cb.onReady(msg.session_id)
        else if (msg.type === 'partial') this.cb.onPartial(msg.text)
        else if (msg.type === 'final') this.cb.onFinal(msg.text, msg.session_id)
        else if (msg.type === 'error') this.cb.onError?.(msg.message)
      } catch {
        // 忽略无法解析的消息
      }
    }
    this.ws = ws
  }

  sendAudio(buf: ArrayBuffer): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(buf)
    }
  }

  close(): void {
    this.ws?.close()
    this.ws = null
  }
}
