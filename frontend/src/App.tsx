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

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Controls
        isCapturing={isCapturing}
        onStart={onStart}
        onStop={onStop}
        onSuggest={chat.generate}
        onClear={chat.clear}
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
