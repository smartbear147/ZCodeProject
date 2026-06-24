import { useCallback, useState } from 'react'
import { postClear, postSuggest, streamAsk } from '../api/chat'
import type { ChatMessage } from '../types'

/**
 * 管理建议 + 追问：generate 同步拿建议，ask 流式追问，clear 清空。
 */
export function useChat(sessionId: string) {
  const [suggestion, setSuggestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState('')
  const [followups, setFollowups] = useState<ChatMessage[]>([])
  const [error, setError] = useState('')

  const generate = useCallback(async (): Promise<boolean> => {
    if (!sessionId) return false
    setLoading(true)
    setError('')
    setSuggestion('')
    try {
      const res = await postSuggest(sessionId)
      setSuggestion(res.suggestion)
      return true
    } catch (e) {
      setError((e as Error).message)
      return false
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  const ask = useCallback(
    async (message: string) => {
      if (!sessionId) return
      setFollowups((prev) => [...prev, { role: 'user', content: message }])
      setStreaming('')
      try {
        let acc = ''
        for await (const delta of streamAsk(sessionId, message)) {
          acc += delta
          setStreaming(acc)
        }
        setFollowups((prev) => [...prev, { role: 'assistant', content: acc }])
      } catch (e) {
        setFollowups((prev) => [
          ...prev,
          { role: 'assistant', content: `（出错）${(e as Error).message}` },
        ])
      } finally {
        setStreaming('')
      }
    },
    [sessionId],
  )

  const clear = useCallback(async () => {
    if (!sessionId) return
    await postClear(sessionId)
    setSuggestion('')
    setFollowups([])
    setError('')
  }, [sessionId])

  return { suggestion, loading, streaming, followups, error, generate, ask, clear }
}
