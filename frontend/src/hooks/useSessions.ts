import { useCallback, useEffect, useState } from 'react'
import {
  createSession,
  deleteSession,
  listSessions,
  type SessionSummary,
} from '../api/chat'

const LAST_SESSION_KEY = 'interview:last_session_id'

/**
 * 会话管理：会话列表 + 当前会话 id（像 ChatGPT 那样）。
 *
 * - 挂载时拉列表；从 localStorage 读上次会话，没有则新建一个。
 * - 当前 sessionId 变化时通知上层重载历史。
 * - 发消息后调 refresh() 更新列表（标题可能变化）。
 */
export function useSessions() {
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [currentId, setCurrentId] = useState('')
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      setSessions(await listSessions())
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      // 先拉列表，有会话则进最近的（或恢复 localStorage 记的），没有则保持空（不自动建）
      try {
        const list = await listSessions()
        if (cancelled) return
        setSessions(list)
        const last = localStorage.getItem(LAST_SESSION_KEY) ?? ''
        if (last && list.some((s) => s.session_id === last)) {
          setCurrentId(last)
        } else if (list.length > 0) {
          setCurrentId(list[0].session_id)
        }
        // 列表为空时 currentId 保持 ''，前端显示"新建对话"引导
      } catch (e) {
        if (!cancelled) setError((e as Error).message)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  // 新建会话：建空会话，切到它，记 localStorage，刷新列表。
  const createNew = useCallback(async () => {
    try {
      const newId = await createSession()
      localStorage.setItem(LAST_SESSION_KEY, newId)
      setCurrentId(newId)
      setSessions(await listSessions())
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  // 切换会话：更新当前 id（上层监听 currentId 重载历史）。
  const switchTo = useCallback((sessionId: string) => {
    localStorage.setItem(LAST_SESSION_KEY, sessionId)
    setCurrentId(sessionId)
  }, [])

  // 删除会话：删掉，若删的是当前会话则切到列表第一个（或新建）。
  const remove = useCallback(
    async (sessionId: string) => {
      try {
        await deleteSession(sessionId)
        const list = await listSessions()
        setSessions(list)
        if (sessionId === currentId) {
          if (list.length > 0) {
            switchTo(list[0].session_id)
          } else {
            // 全删空了，保持空状态，让用户手动新建
            setCurrentId('')
          }
        }
      } catch (e) {
        setError((e as Error).message)
      }
    },
    [currentId, switchTo],
  )

  return {
    sessions,
    currentId,
    error,
    refresh,
    createNew,
    switchTo,
    remove,
  }
}
