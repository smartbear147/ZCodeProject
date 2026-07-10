import { useEffect, useRef } from 'react'
import type { SubtitleLine } from '../types'

interface Props {
  lines: SubtitleLine[]
  currentPartial: string
  onRemoveLine: (index: number) => void
  onClearAll: () => void
  /** 把字幕区全部内容作为一条消息发给 LLM（发送后字幕区清空）。 */
  onSendSubtitles: () => void
}

export function SubtitlePanel({
  lines,
  currentPartial,
  onRemoveLine,
  onClearAll,
  onSendSubtitles,
}: Props) {
  const bottomRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, currentPartial])

  return (
    <section className="panel-card subtitle-card" aria-label="实时字幕">
      <header className="panel-header">
        <h2>实时字幕</h2>
        <div className="header-actions">
          {lines.length > 0 && (
            <>
              <button
                type="button"
                className="accent-control"
                onClick={onSendSubtitles}
              >
                发送字幕
              </button>
              <button type="button" className="text-btn" onClick={onClearAll}>
                清空字幕
              </button>
            </>
          )}
        </div>
      </header>
      <div className="subtitle-content">
        {lines.length === 0 && !currentPartial && (
          <p className="empty-state">
            点"开始采集"后，面试官的话会出现在这里。打字聊天请用右侧对话区。
          </p>
        )}
        {lines.map((line, index) => (
          <div key={index} className="subtitle-line-row">
            <p className="subtitle-line">{line.text}</p>
            <button
              type="button"
              className="line-remove-btn"
              aria-label="删除该行"
              onClick={() => onRemoveLine(index)}
            >
              ×
            </button>
          </div>
        ))}
        {currentPartial && (
          <p className="subtitle-partial">
            <span>识别中</span>
            {currentPartial}
          </p>
        )}
        <div ref={bottomRef} />
      </div>
    </section>
  )
}
