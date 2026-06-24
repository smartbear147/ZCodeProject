import { useCallback } from 'react'
import { Controls } from './components/Controls'
import { SubtitlePanel } from './components/SubtitlePanel'
import { SuggestPanel } from './components/SuggestPanel'
import { useAudioCapture } from './hooks/useAudioCapture'
import { useChat } from './hooks/useChat'
import { useSubtitle } from './hooks/useSubtitle'

function App() {
  const subtitle = useSubtitle()
  const chat = useChat(subtitle.sessionId)

  const handleChunk = useCallback(
    (buf: ArrayBuffer) => subtitle.sendAudio(buf),
    [subtitle],
  )
  const { isCapturing, start, stop, error: captureError } =
    useAudioCapture(handleChunk)

  const onStart = async () => {
    subtitle.connect()
    await start()
  }
  const onStop = () => {
    stop()
    subtitle.close()
  }

  // 生成建议：成功后清空左侧字幕（这轮的话已送走，开始新一轮），
  // 与后端 current_turn_text 清空保持一致。失败不清空，保留字幕方便重试。
  const onSuggest = useCallback(async () => {
    const ok = await chat.generate()
    if (ok) {
      subtitle.clearLines()
    }
  }, [chat, subtitle])

  const onClear = useCallback(async () => {
    await chat.clear()
    subtitle.clearLines()
  }, [chat, subtitle])

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Controls
        isCapturing={isCapturing}
        onStart={onStart}
        onStop={onStop}
        onSuggest={onSuggest}
        onClear={onClear}
      />
      {(captureError || subtitle.error) && (
        <div style={{ padding: '6px 12px', background: '#fff3f3', color: '#c00' }}>
          {captureError || subtitle.error}
        </div>
      )}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <div
          style={{
            flex: 1,
            borderRight: '1px solid #e0e0e0',
            minHeight: 0,
          }}
        >
          <SubtitlePanel
            lines={subtitle.lines}
            currentPartial={subtitle.currentPartial}
          />
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <SuggestPanel
            suggestion={chat.suggestion}
            loading={chat.loading}
            streaming={chat.streaming}
            followups={chat.followups}
            error={chat.error}
            onAsk={chat.ask}
          />
        </div>
      </div>
    </div>
  )
}

export default App
