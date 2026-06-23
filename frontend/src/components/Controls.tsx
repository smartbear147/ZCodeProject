interface Props {
  isCapturing: boolean
  onStart: () => void
  onStop: () => void
  onSuggest: () => void
  onClear: () => void
}

export function Controls({
  isCapturing,
  onStart,
  onStop,
  onSuggest,
  onClear,
}: Props) {
  return (
    <div
      style={{
        display: 'flex',
        gap: 8,
        padding: 12,
        borderBottom: '1px solid #e0e0e0',
        alignItems: 'center',
      }}
    >
      <strong style={{ marginRight: 'auto' }}>面试助手</strong>
      {isCapturing ? (
        <button onClick={onStop}>⏹ 停止采集</button>
      ) : (
        <button onClick={onStart}>▶ 开始采集</button>
      )}
      <button onClick={onSuggest}>✨ 生成建议</button>
      <button onClick={onClear}>🗑 清空上下文</button>
    </div>
  )
}
