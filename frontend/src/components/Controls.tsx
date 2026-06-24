import type { AudioInputDevice } from '../hooks/useDevices'

interface Props {
  isCapturing: boolean
  level: number
  devices: AudioInputDevice[]
  selectedDeviceId: string
  onSelectDevice: (deviceId: string) => void
  onStart: () => void
  onStop: () => void
  onSuggest: () => void
  onClear: () => void
}

export function Controls({
  isCapturing,
  level,
  devices,
  selectedDeviceId,
  onSelectDevice,
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
        flexWrap: 'wrap',
      }}
    >
      <strong style={{ marginRight: 'auto' }}>面试助手</strong>

      <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        输入设备
        <select
          value={selectedDeviceId}
          onChange={(e) => onSelectDevice(e.target.value)}
          style={{ maxWidth: 220 }}
          title="选择虚拟声卡：macOS 选 BlackHole；Windows 选 VoiceMeeter Output"
        >
          <option value="">（默认 / 未选择）</option>
          {devices.map((d) => (
            <option key={d.deviceId} value={d.deviceId}>
              {d.label}
            </option>
          ))}
        </select>
      </label>

      {/* 实时输入电平：宽度随 level 变化；静音灰、有声绿 */}
      <div
        title="实时输入电平（无声时检查是否抓错了真实麦克风）"
        style={{
          width: 120,
          height: 8,
          background: '#e0e0e0',
          borderRadius: 4,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${level}%`,
            height: '100%',
            background: level > 2 ? '#4caf50' : '#bbb',
            transition: 'width 80ms linear',
          }}
        />
      </div>

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
