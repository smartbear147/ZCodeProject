import { useState } from 'react'
import type { ChatMessage } from '../types'

interface Props {
  suggestion: string
  loading: boolean
  streaming: string
  followups: ChatMessage[]
  error: string
  onAsk: (msg: string) => void
}

export function SuggestPanel({
  suggestion,
  loading,
  streaming,
  followups,
  error,
  onAsk,
}: Props) {
  const [input, setInput] = useState('')
  const send = () => {
    if (input.trim()) {
      onAsk(input.trim())
      setInput('')
    }
  }

  return (
    <div
      style={{
        height: '100%',
        padding: 12,
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <h3 style={{ marginTop: 0 }}>回答建议</h3>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {loading ? (
          <p style={{ color: '#888' }}>生成中...</p>
        ) : suggestion ? (
          <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.7 }}>{suggestion}</p>
        ) : (
          <p style={{ color: '#aaa' }}>
            面试官问完后，点"生成建议"获取回答思路。
          </p>
        )}
        {error && <p style={{ color: '#c00' }}>{error}</p>}
        {streaming && (
          <p style={{ color: '#555', whiteSpace: 'pre-wrap' }}>{streaming}</p>
        )}
        {followups.length > 0 && <hr style={{ margin: '12px 0' }} />}
        {followups.map((m, i) => (
          <p
            key={i}
            style={{
              textAlign: m.role === 'user' ? 'right' : 'left',
              margin: '6px 0',
            }}
          >
            <strong>{m.role === 'user' ? '你' : '助手'}：</strong>
            <span style={{ whiteSpace: 'pre-wrap' }}>{m.content}</span>
          </p>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') send()
          }}
          placeholder="追问（如：再详细点 / 换个角度）"
          style={{ flex: 1 }}
        />
        <button onClick={send}>发送</button>
      </div>
    </div>
  )
}
