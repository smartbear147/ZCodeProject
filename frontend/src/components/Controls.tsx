import { Link } from 'react-router-dom'
import type { AudioInputDevice } from '../hooks/useDevices'

interface Props {
  isCapturing: boolean
  level: number
  devices: AudioInputDevice[]
  selectedDeviceId: string
  onSelectDevice: (deviceId: string) => void
  onStart: () => void
  onStop: () => void
  sidebarCollapsed: boolean
  onToggleSidebar: () => void
}

export function Controls({
  isCapturing,
  level,
  devices,
  selectedDeviceId,
  onSelectDevice,
  onStart,
  onStop,
  sidebarCollapsed,
  onToggleSidebar,
}: Props) {
  return (
    <header className="topbar">
      <button
        type="button"
        className="sidebar-toggle"
        onClick={onToggleSidebar}
        aria-label={sidebarCollapsed ? '展开会话列表' : '收起会话列表'}
        title={sidebarCollapsed ? '展开会话列表' : '收起会话列表'}
      >
        {sidebarCollapsed ? '☰' : '✕'}
      </button>
      <div className="brand">
        <span className="brand-icon" aria-hidden="true">✓</span>
        <strong>面试助手</strong>
      </div>
      <select
        className="device-select"
        aria-label="输入设备"
        value={selectedDeviceId}
        onChange={(e) => onSelectDevice(e.target.value)}
      >
        <option value="">默认设备</option>
        {devices.map((d) => (
          <option key={d.deviceId} value={d.deviceId}>
            {d.label}
          </option>
        ))}
      </select>
      <div
        className="level-meter"
        role="meter"
        aria-label="输入音量"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={level}
      >
        <div className="level-meter-fill" style={{ width: `${level}%` }} />
      </div>
      <div
        className={`capture-status ${isCapturing ? 'is-active' : ''}`}
        role="status"
        aria-live="polite"
      >
        <span aria-hidden="true" className="status-dot" />
        {isCapturing ? '正在采集' : '等待采集'}
      </div>
      {isCapturing ? (
        <button className="primary-control" onClick={onStop}>⏹ 停止采集</button>
      ) : (
        <button className="primary-control" onClick={onStart}>▶ 开始采集</button>
      )}
      <Link to="/manage" className="secondary-control manage-btn">
        📁 管理
      </Link>
    </header>
  )
}
