import { useState } from 'react'

interface Props {
  onUpload: (file: File, docType: 'resume' | 'qa') => void
}

/**
 * 文档上传区：文件选择 + 类型单选（简历/题库）+ 上传按钮。
 */
export function DocumentUpload({ onUpload }: Props) {
  const [docType, setDocType] = useState<'resume' | 'qa'>('resume')
  const [file, setFile] = useState<File | null>(null)

  const submit = () => {
    if (file) {
      onUpload(file, docType)
      setFile(null)
    }
  }

  return (
    <div className="upload-box">
      <label className="file-dropzone">
        <input
          type="file"
          accept=".pdf,.md"
          aria-label="选择要上传的 PDF 或 Markdown 文档"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <span className="file-dropzone-icon">📎</span>
        <span className="file-dropzone-title">
          {file ? file.name : '选择 PDF / Markdown 文档'}
        </span>
        <span className="file-dropzone-subtitle">
          {file ? `${(file.size / 1024).toFixed(1)}KB，准备上传` : '点击选择文件，用作面试回答上下文'}
        </span>
      </label>
      <div className="doc-type-radios">
        <label className={docType === 'resume' ? 'is-selected' : ''}>
          <input
            type="radio"
            checked={docType === 'resume'}
            onChange={() => setDocType('resume')}
          />
          <span>简历</span>
        </label>
        <label className={docType === 'qa' ? 'is-selected' : ''}>
          <input
            type="radio"
            checked={docType === 'qa'}
            onChange={() => setDocType('qa')}
          />
          <span>面试题库</span>
        </label>
      </div>
      <button className="upload-submit" type="button" onClick={submit} disabled={!file}>
        {file ? '上传到知识库' : '先选择文件'}
      </button>
      <p className="hint">支持 PDF（.pdf）、Markdown（.md）</p>
    </div>
  )
}
