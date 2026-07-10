import { Link } from 'react-router-dom'
import { DocumentList } from '../components/DocumentList'
import { DocumentUpload } from '../components/DocumentUpload'
import { useDocuments } from '../hooks/useDocuments'

/**
 * 管理页：上传简历(PDF)/面试题库(.md)，查看并删除已上传文档。
 */
function ManagePage() {
  const { documents, loading, error, upload, remove } = useDocuments()
  const resumeCount = documents.filter((doc) => doc.doc_type === 'resume').length
  const qaCount = documents.filter((doc) => doc.doc_type === 'qa').length

  return (
    <main className="app-shell">
      <div className="app-frame manage-frame">
        <header className="manage-header">
          <div>
            <Link to="/" className="back-link">
              ← 返回面试
            </Link>
            <h1>面试助手 · 管理</h1>
            <p>
              上传简历和题库后，生成回答时会优先参考这些材料，让回答更贴近你的真实经历。
            </p>
          </div>
          <div className="manage-summary" aria-label="文档统计">
            <span>
              <strong>{documents.length}</strong>
              份文档
            </span>
            <span>
              <strong>{resumeCount}</strong>
              份简历
            </span>
            <span>
              <strong>{qaCount}</strong>
              份题库
            </span>
          </div>
        </header>

        <div className="manage-grid">
          <section className="manage-section upload-section" aria-labelledby="upload-title">
            <div className="section-heading">
              <span className="section-kicker">Context</span>
              <h2 id="upload-title">上传文档</h2>
              <p>支持 PDF 简历和 Markdown 面试题库，上传后立即进入回答上下文。</p>
            </div>
            <DocumentUpload onUpload={upload} />
          </section>

          <section className="manage-section list-section" aria-labelledby="document-list-title">
            <div className="section-heading">
              <span className="section-kicker">Library</span>
              <h2 id="document-list-title">已上传文档</h2>
              <p>删除不再使用的材料，避免旧内容干扰后续回答。</p>
            </div>
            {error && (
              <div className="error-banner" role="alert">
                {error}
              </div>
            )}
            {loading && documents.length === 0 ? (
              <p className="empty-state">加载中...</p>
            ) : (
              <DocumentList documents={documents} onDelete={remove} />
            )}
          </section>
        </div>
      </div>
    </main>
  )
}

export default ManagePage
