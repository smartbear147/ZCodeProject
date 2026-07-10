@echo off
cd /d "%~dp0"

if "%~1"=="backend" goto backend
if "%~1"=="frontend" goto frontend

echo.
echo ============================================
echo   面试助手 - 启动
echo ============================================
echo.

echo 正在启动后端与前端（首次运行需安装依赖，请耐心等待）...
start "面试助手-后端 (port 8000)" "%~f0" backend
start "面试助手-前端 (port 5173)" "%~f0" frontend

echo.
echo 已在新窗口启动：
echo   后端: http://localhost:8000  (健康检查 /health)
echo   前端: http://localhost:5173  ^<- 浏览器访问这个
echo.
echo 关闭弹出的两个窗口即可停止服务。
echo.
pause
exit /b

:backend
cd backend
if not exist ".venv\Scripts\activate.bat" (
    python --version 2>nul || (echo [错误] 未找到 Python，请先安装 Python 3.11+ ^& pause ^& exit /b 1)
    echo [后端] 首次运行：创建虚拟环境并安装依赖（可能需要几分钟）...
    python -m venv .venv
    call ".venv\Scripts\activate.bat"
    pip install -e ".[dev]"
)
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [后端] 已从 .env.example 创建 .env，请编辑 backend/.env 填入你的 API 密钥后再重启。
        echo [后端] 按任意键退出...
        pause >nul
        exit /b 1
    )
)
call ".venv\Scripts\activate.bat"
echo [后端] 启动 uvicorn...
uvicorn app.main:app --reload --port 8000
echo.
echo [后端] 已停止（如非预期，请查看上方错误信息）。
pause
exit /b

:frontend
cd frontend
node --version 2>nul || (echo [错误] 未找到 Node.js，请先安装 Node.js ^& pause ^& exit /b 1)
if not exist "node_modules\.package-lock.json" (
    echo [前端] 首次运行：安装依赖...
    call npm install
)
echo [前端] 启动 vite...
call npm run dev
echo.
echo [前端] 已停止（如非预期，请查看上方错误信息）。
pause
exit /b