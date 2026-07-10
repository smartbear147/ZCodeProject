import type { DocumentInfo } from '../types'

const BASE = '/api/documents'

export async function listDocuments(): Promise<DocumentInfo[]> {
  const resp = await fetch(`${BASE}/list`)
  if (!resp.ok) throw new Error(`获取文档列表失败：${resp.status}`)
  const data = await resp.json()
  return data.documents as DocumentInfo[]
}

export async function uploadDocument(
  file: File,
  docType: 'resume' | 'qa',
): Promise<DocumentInfo> {
  const form = new FormData()
  form.append('file', file)
  form.append('doc_type', docType)
  const resp = await fetch(`${BASE}/upload`, {
    method: 'POST',
    body: form,
  })
  if (!resp.ok) {
    const detail = await resp.text()
    throw new Error(`上传失败：${detail}`)
  }
  return resp.json()
}

export async function deleteDocument(id: string): Promise<void> {
  const resp = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  if (!resp.ok) throw new Error(`删除失败：${resp.status}`)
}
