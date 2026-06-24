import { useCallback, useEffect, useState } from 'react'

export interface AudioInputDevice {
  deviceId: string
  label: string
}

/**
 * 枚举音频输入设备。
 *
 * 浏览器要求先有 getUserMedia 授权，enumerateDevices 返回的设备才带 label
 * （否则 label 为空、deviceId 为空字符串）。所以调用方需在首次 getUserMedia
 * 成功后调用 refresh() 重新拉取，下拉框才会显示真实设备名（如 Voicemeeter Out）。
 *
 * 监听 devicechange，设备插拔时自动刷新。
 */
export function useDevices() {
  const [devices, setDevices] = useState<AudioInputDevice[]>([])

  const refresh = useCallback(async () => {
    const all = await navigator.mediaDevices.enumerateDevices()
    setDevices(
      all
        .filter((d) => d.kind === 'audioinput')
        .map((d) => ({ deviceId: d.deviceId, label: d.label || '未命名设备' })),
    )
  }, [])

  useEffect(() => {
    const handler = () => {
      void refresh()
    }
    // 部分浏览器没有 addEventListener，做防御
    navigator.mediaDevices.addEventListener?.('devicechange', handler)
    return () => {
      navigator.mediaDevices.removeEventListener?.('devicechange', handler)
    }
  }, [refresh])

  return { devices, refresh }
}
