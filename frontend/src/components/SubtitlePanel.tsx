import { useEffect, useRef } from 'react'
import type { SubtitleLine } from '../types'

interface Props {
  lines: SubtitleLine[]
  currentPartial: string
}

export function SubtitlePanel({ lines, currentPartial }: Props) {
  // 自动滚到底部
  const bottomRef = useRef<HTMLDivElement | null>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, currentPartial])

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: 12 }}>
      {lines.length === 0 && !currentPartial && (
        <p style={{ color: '#aaa' }}>点"开始采集"后，面试官的话会出现在这里。</p>
      )}
      {lines.map((l, i) => (
        <p key={i} style={{ margin: '6px 0', lineHeight: 1.6 }}>
          {l.text}
        </p>
      ))}
      {currentPartial && (
        <p style={{ color: '#999', margin: '6px 0', lineHeight: 1.6 }}>
          {currentPartial} <span>（识别中）</span>
        </p>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
