import { useCallback, useEffect, useState } from 'react'
import { deleteDocument, listDocuments, uploadDocument } from '../api/documents'
import type { DocumentInfo } from '../types'

/**
 * 文档管理：列表 / 上传 / 删除。
 * 挂载时自动拉一次列表。
 */
export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setDocuments(await listDocuments())
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const upload = useCallback(
    async (file: File, docType: 'resume' | 'qa') => {
      setError('')
      try {
        await uploadDocument(file, docType)
        await refresh()
      } catch (e) {
        setError((e as Error).message)
      }
    },
    [refresh],
  )

  const remove = useCallback(
    async (id: string) => {
      setError('')
      try {
        await deleteDocument(id)
        await refresh()
      } catch (e) {
        setError((e as Error).message)
      }
    },
    [refresh],
  )

  return { documents, loading, error, refresh, upload, remove }
}
