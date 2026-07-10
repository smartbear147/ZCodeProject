/** 后端对话 + 字幕 API 客户端。 */

const BASE = '/api'

/** 创建一个新会话，返回 session_id。 */
export async function createSession(): Promise<string> {
  const resp = await fetch(`${BASE}/session`, { method: 'POST' })
  if (!resp.ok) throw new Error(`创建会话失败：${resp.status}`)
  const data = await resp.json()
  return data.session_id as string
}

export interface SessionSummary {
  session_id: string
  title: string
  updated_at: number
}

export interface SessionDetail {
  session_id: string
  title: string | null
  messages: { role: string; content: string }[]
  subtitle_lines: string[]
}

/** 列出所有会话摘要（按更新时间倒序）。 */
export async function listSessions(): Promise<SessionSummary[]> {
  const resp = await fetch(`${BASE}/sessions`)
  if (!resp.ok) throw new Error(`获取会话列表失败：${resp.status}`)
  const data = await resp.json()
  return data.sessions as SessionSummary[]
}

/** 获取某个会话的完整内容（切换会话时加载历史）。 */
export async function getSession(sessionId: string): Promise<SessionDetail> {
  const resp = await fetch(`${BASE}/session/${sessionId}`)
  if (!resp.ok) throw new Error(`获取会话失败：${resp.status}`)
  return resp.json()
}

/** 删除某个会话。 */
export async function deleteSession(sessionId: string): Promise<void> {
  const resp = await fetch(`${BASE}/session/${sessionId}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`删除会话失败：${resp.status}`)
}

/** 重命名某个会话。返回新标题。 */
export async function renameSession(
  sessionId: string,
  title: string,
): Promise<string> {
  const resp = await fetch(`${BASE}/session/rename`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, title }),
  })
  if (!resp.ok) throw new Error(`重命名失败：${resp.status}`)
  const data = await resp.json()
  return data.title as string
}

/** SSE 流式读取通用工具：把 fetch 的 SSE 响应逐 token yield。 */
async function* readSseStream(
  resp: Response,
  failMsg: string,
): AsyncGenerator<string> {
  if (!resp.ok || !resp.body) throw new Error(`${failMsg}：${resp.status}`)
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const payload = JSON.parse(line.slice(6))
          if (payload.delta) yield payload.delta as string
          else if (payload.error) throw new Error(payload.error)
        } catch {
          // 忽略不完整的 JSON
        }
      }
    }
  }
}

/** 发送一条消息（或字幕区全部内容）给 LLM，流式返回回复。 */
export async function* sendChat(
  sessionId: string,
  body: { message?: string; send_subtitles?: boolean },
): AsyncGenerator<string> {
  const resp = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, ...body }),
  })
  yield* readSseStream(resp, '对话失败')
}

/** 清空整个对话历史（字幕区不动）。 */
export async function resetChat(sessionId: string): Promise<void> {
  const resp = await fetch(`${BASE}/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!resp.ok) throw new Error(`重置失败：${resp.status}`)
}

/** 删除字幕区某一行。返回剩余行。 */
export async function removeSubtitleLine(
  sessionId: string,
  lineIndex: number,
): Promise<string[]> {
  const resp = await fetch(`${BASE}/subtitle/remove-line`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, line_index: lineIndex }),
  })
  if (!resp.ok) throw new Error(`删除失败：${resp.status}`)
  const data = await resp.json()
  return data.remaining_lines as string[]
}

/** 清空字幕区（不影响对话历史）。 */
export async function clearSubtitle(sessionId: string): Promise<void> {
  const resp = await fetch(`${BASE}/subtitle/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  })
  if (!resp.ok) throw new Error(`清空字幕失败：${resp.status}`)
}
