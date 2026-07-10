import { BrowserRouter, Route, Routes } from 'react-router-dom'
import InterviewPage from './routes/InterviewPage'
import ManagePage from './routes/ManagePage'

/**
 * 应用根：路由壳。
 * /        面试助手页
 * /manage  简历/文档管理页
 */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<InterviewPage />} />
        <Route path="/manage" element={<ManagePage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
