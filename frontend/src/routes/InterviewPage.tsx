import { useCallback, useState } from 'react'
import { ChatPanel } from '../components/ChatPanel'
import { Controls } from '../components/Controls'
import { SessionSidebar } from '../components/SessionSidebar'
import { SubtitlePanel } from '../components/SubtitlePanel'
import { useAudioCapture } from '../hooks/useAudioCapture'
import { useChat } from '../hooks/useChat'
import { useDevices } from '../hooks/useDevices'
import { useSessions } from '../hooks/useSessions'
import { useSubtitle } from '../hooks/useSubtitle'

/**
 * 面试助手页：左侧会话列表 + 字幕区 + 右侧对话区。
 * 像 ChatGPT 那样支持多会话切换，侧边栏可收起。
 */
function InterviewPage() {
  const sessions = useSessions()
  const sessionId = sessions.currentId
  const subtitle = useSubtitle(sessionId)
  const chat = useChat(sessionId)
  const { devices, refresh: refreshDevices } = useDevices()
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
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

  // 发送字幕后刷新会话列表（标题可能因首条消息变化）
  const onSendSubtitles = useCallback(async () => {
    const text = subtitle.lines.map((l) => l.text).join('\n').trim()
    if (!text) return
    const ok = await chat.sendSubtitles(text)
    if (ok) {
      subtitle.clearLines()
      sessions.refresh()
    }
  }, [chat, subtitle, sessions])

  const onManualSend = useCallback(
    async (message: string) => {
      await chat.send(message)
      sessions.refresh()
    },
    [chat, sessions],
  )

  const onReset = useCallback(async () => {
    await chat.reset()
    sessions.refresh()
  }, [chat, sessions])

  return (
    <main className="app-shell">
      <div className="app-frame app-frame-with-sidebar">
        <SessionSidebar
          sessions={sessions.sessions}
          currentId={sessionId}
          collapsed={sidebarCollapsed}
          onSelect={sessions.switchTo}
          onCreate={sessions.createNew}
          onDelete={sessions.remove}
          onToggleCollapse={() => setSidebarCollapsed((v) => !v)}
        />
        <div className="app-main">
          <Controls
            isCapturing={isCapturing}
            level={level}
            devices={devices}
            selectedDeviceId={selectedDeviceId}
            onSelectDevice={onSelectDevice}
            onStart={onStart}
            onStop={onStop}
            sidebarCollapsed={sidebarCollapsed}
            onToggleSidebar={() => setSidebarCollapsed((v) => !v)}
          />
          {(captureError || subtitle.error || sessions.error) && (
            <div className="error-banner" role="alert">
              {captureError || subtitle.error || sessions.error}
            </div>
          )}
          {sessionId ? (
            <section className="workspace" aria-label="面试辅助工作区">
              <SubtitlePanel
                lines={subtitle.lines}
                currentPartial={subtitle.currentPartial}
                onRemoveLine={subtitle.removeLine}
                onClearAll={subtitle.clearAll}
                onSendSubtitles={onSendSubtitles}
              />
              <ChatPanel
                messages={chat.messages}
                streaming={chat.streaming}
                loading={chat.loading}
                error={chat.error}
                onSend={onManualSend}
                onReset={onReset}
              />
            </section>
          ) : (
            <div className="empty-main-state">
              <p>还没有会话，点左侧「+ 新建对话」开始。</p>
            </div>
          )}
        </div>
      </div>
    </main>
  )
}

export default InterviewPage
