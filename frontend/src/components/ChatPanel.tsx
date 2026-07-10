import { useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../types'

interface Props {
  messages: ChatMessage[]
  streaming: string
  loading: boolean
  error: string
  onSend: (message: string) => void
  onReset: () => void
}

/**
 * 纯聊天面板：像 ChatGPT 一样，显示对话历史 + 输入框。
 * 历史永远累积，清空靠"重置对话"按钮。
 */
export function ChatPanel({
  messages,
  streaming,
  loading,
  error,
  onSend,
  onReset,
}: Props) {
  const bottomRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streaming])

  const [input, setInput] = useState('')
  const submit = () => {
    const msg = input.trim()
    if (msg) {
      onSend(msg)
      setInput('')
    }
  }

  return (
    <section className="panel-card chat-card" aria-label="对话">
      <header className="panel-header">
        <h2>对话</h2>
        {messages.length > 0 && (
          <button type="button" className="text-btn" onClick={onReset}>
            重置对话
          </button>
        )}
      </header>
      <div className="chat-content">
        {messages.length === 0 && !streaming && (
          <p className="empty-state">
            点"发送字幕"把面试官的话发过来，或在下方直接输入。
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`chat-message is-${m.role}`}
          >
            <strong>{m.role === 'user' ? '我' : '助手'}</strong>
            <span>{m.content}</span>
          </div>
        ))}
        {streaming && (
          <div className="chat-message is-assistant">
            <strong>助手</strong>
            <span>{streaming}</span>
          </div>
        )}
        {error && <div className="error-banner" role="alert">{error}</div>}
        <div ref={bottomRef} />
      </div>
      <form
        className="chat-form"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <input
          aria-label="输入消息"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入消息，回车发送"
        />
        <button type="submit" disabled={loading}>
          发送
        </button>
      </form>
    </section>
  )
}
