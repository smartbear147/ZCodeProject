import { useCallback, useEffect, useState } from 'react'
import { getSession, resetChat, sendChat } from '../api/chat'
import type { ChatMessage } from '../types'

/**
 * 纯聊天：一个不断累积的对话历史，绑定到指定 sessionId。
 *
 * - sessionId 变化时：从后端拉该会话的历史，填充 messages（切换会话恢复）。
 * - send(message)：手打一条消息，流式追加 user+assistant。
 * - sendSubtitles(subtitleText)：把字幕区全部内容作为一条 user 消息发出。
 * - reset()：清空整个对话历史。
 */
export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // 切换会话时从后端加载历史
  useEffect(() => {
    if (!sessionId) {
      setMessages([])
      return
    }
    let cancelled = false
    setError('')
    getSession(sessionId)
      .then((detail) => {
        if (cancelled) return
        setMessages(
          detail.messages.map((m) => ({
            role: m.role as 'user' | 'assistant',
            content: m.content,
          })),
        )
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message)
      })
    return () => {
      cancelled = true
    }
  }, [sessionId])

  // 流式发送：把 user 消息先显示，再请求后端拿流式 assistant 回复。
  const sendStream = useCallback(
    async (
      body: { message?: string; send_subtitles?: boolean },
      displayText: string,
    ): Promise<boolean> => {
      if (!sessionId) return false
      setLoading(true)
      setError('')
      setStreaming('')
      setMessages((prev) => [...prev, { role: 'user', content: displayText }])
      try {
        let acc = ''
        for await (const delta of sendChat(sessionId, body)) {
          acc += delta
          setStreaming(acc)
        }
        setMessages((prev) => [...prev, { role: 'assistant', content: acc }])
        return true
      } catch (e) {
        setError((e as Error).message)
        return false
      } finally {
        setStreaming('')
        setLoading(false)
      }
    },
    [sessionId],
  )

  const send = useCallback(
    (message: string) => sendStream({ message }, message),
    [sendStream],
  )

  const sendSubtitles = useCallback(
    (subtitleText: string) => sendStream({ send_subtitles: true }, subtitleText),
    [sendStream],
  )

  const reset = useCallback(async () => {
    if (!sessionId) return
    setError('')
    try {
      await resetChat(sessionId)
      setMessages([])
    } catch (e) {
      setError((e as Error).message)
    }
  }, [sessionId])

  return { messages, streaming, loading, error, send, sendSubtitles, reset }
}
