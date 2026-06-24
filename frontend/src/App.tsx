import { useCallback, useState } from 'react'
import { Controls } from './components/Controls'
import { SubtitlePanel } from './components/SubtitlePanel'
import { SuggestPanel } from './components/SuggestPanel'
import { useAudioCapture } from './hooks/useAudioCapture'
import { useChat } from './hooks/useChat'
import { useDevices } from './hooks/useDevices'
import { useSubtitle } from './hooks/useSubtitle'

function App() {
  const subtitle = useSubtitle()
  const chat = useChat(subtitle.sessionId)
  const { devices, refresh: refreshDevices } = useDevices()
  const [selectedDeviceId, setSelectedDeviceId] = useState('')

  const handleChunk = useCallback(
    (buf: ArrayBuffer) => subtitle.sendAudio(buf),
    [subtitle],
  )
  const { isCapturing, level, start, stop, error: captureError } =
    useAudioCapture(handleChunk, selectedDeviceId)

  const onStart = async () => {
    subtitle.connect()
    await start()
    // 授权后刷新设备列表，让下拉框显示真实设备名（VoiceMeeter Output 等）
    refreshDevices()
  }
  const onStop = () => {
    stop()
    subtitle.close()
  }

  // 切换设备：更新选中态；若正在采集，用新设备重连（显式传 id 绕过 setState 异步）
  const onSelectDevice = useCallback(
    async (deviceId: string) => {
      setSelectedDeviceId(deviceId)
      if (isCapturing) {
        stop()
        await start(deviceId)
      }
    },
    [isCapturing, start, stop],
  )

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
        level={level}
        devices={devices}
        selectedDeviceId={selectedDeviceId}
        onSelectDevice={onSelectDevice}
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
