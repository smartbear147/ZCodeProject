import { useCallback, useRef, useState } from 'react'
import { AsrSocket } from '../api/asrSocket'
import type { SubtitleLine } from '../types'

/**
 * 管理字幕：连 ASR WebSocket，维护当前识别中的句子 + 定稿历史。
 */
export function useSubtitle() {
  const [lines, setLines] = useState<SubtitleLine[]>([])
  const [currentPartial, setCurrentPartial] = useState('')
  const [sessionId, setSessionId] = useState('')
  const [error, setError] = useState('')
  const socketRef = useRef<AsrSocket | null>(null)

  const connect = useCallback(() => {
    const socket = new AsrSocket({
      onReady: (sid) => setSessionId(sid),
      onPartial: (text) => setCurrentPartial(text),
      onFinal: (text) => {
        setCurrentPartial('')
        setLines((prev) => [...prev, { text, isFinal: true }])
      },
      onError: (msg) => setError(msg),
    })
    socket.connect()
    socketRef.current = socket
  }, [])

  const sendAudio = useCallback((buf: ArrayBuffer) => {
    socketRef.current?.sendAudio(buf)
  }, [])

  const close = useCallback(() => {
    socketRef.current?.close()
    socketRef.current = null
  }, [])

  return { lines, currentPartial, sessionId, error, connect, sendAudio, close }
}
