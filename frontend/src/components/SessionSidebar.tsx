import type { SessionSummary } from '../api/chat'

interface Props {
  sessions: SessionSummary[]
  currentId: string
  collapsed: boolean
  onSelect: (sessionId: string) => void
  onCreate: () => void
  onDelete: (sessionId: string) => void
  onToggleCollapse: () => void
}

function formatTime(ts: number): string {
  const d = new Date(ts * 1000)
  const now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  if (sameDay) return `${hh}:${mm}`
  return `${d.getMonth() + 1}/${d.getDate()} ${hh}:${mm}`
}

/**
 * 会话列表侧边栏：新建对话 + 切换 + 删除 + 收起。
 * 收起时变成窄条，只显示新建和展开按钮。
 */
export function SessionSidebar({
  sessions,
  currentId,
  collapsed,
  onSelect,
  onCreate,
  onDelete,
  onToggleCollapse,
}: Props) {
  if (collapsed) {
    return (
      <aside className="session-sidebar is-collapsed" aria-label="会话列表">
        <button
          type="button"
          className="sidebar-icon-btn"
          onClick={onCreate}
          aria-label="新建对话"
          title="新建对话"
        >
          ＋
        </button>
        <button
          type="button"
          className="sidebar-icon-btn"
          onClick={onToggleCollapse}
          aria-label="展开会话列表"
          title="展开会话列表"
        >
          ☰
        </button>
      </aside>
    )
  }

  return (
    <aside className="session-sidebar" aria-label="会话列表">
      <div className="session-sidebar-head">
        <button type="button" className="new-session-btn" onClick={onCreate}>
          + 新建对话
        </button>
        <button
          type="button"
          className="sidebar-collapse-btn"
          onClick={onToggleCollapse}
          aria-label="收起会话列表"
          title="收起会话列表"
        >
          ‹
        </button>
      </div>
      <ul className="session-list">
        {sessions.map((s) => (
          <li
            key={s.session_id}
            className={`session-item ${s.session_id === currentId ? 'is-active' : ''}`}
          >
            <button
              type="button"
              className="session-select"
              onClick={() => onSelect(s.session_id)}
            >
              <span className="session-title">{s.title || '新对话'}</span>
              <span className="session-time">{formatTime(s.updated_at)}</span>
            </button>
            <button
              type="button"
              className="session-delete"
              aria-label="删除会话"
              onClick={(e) => {
                e.stopPropagation()
                onDelete(s.session_id)
              }}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
