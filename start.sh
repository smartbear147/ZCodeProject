#!/usr/bin/env bash
# 面试助手一键启动脚本（macOS / Linux / Git Bash）
# 用法：bash start.sh

set -e
cd "$(dirname "$0")"

cleanup() {
  echo ""
  echo "正在停止所有服务..."
  jobs -p 2>/dev/null | xargs -r kill 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# ---------- 后端 ----------
(
  cd backend
  if [ ! -f ".venv/bin/activate" ]; then
    echo "[后端] 首次运行：创建虚拟环境并安装依赖（可能需要几分钟）..."
    python3 -m venv .venv
    # shellcheck disable=SC1091
    . .venv/bin/activate
    pip install -e ".[dev]"
  fi
  # shellcheck disable=SC1091
  . .venv/bin/activate
  echo "[后端] 启动 uvicorn (:8000)..."
  uvicorn app.main:app --reload --port 8000
) &

# ---------- 前端 ----------
(
  cd frontend
  if [ ! -d "node_modules" ]; then
    echo "[前端] 首次运行：安装依赖..."
    npm install
  fi
  echo "[前端] 启动 vite (:5173)..."
  npm run dev
) &

echo ""
echo "============================================"
echo "  面试助手 - 启动中"
echo "============================================"
echo "  后端: http://localhost:8000  (健康检查 /health)"
echo "  前端: http://localhost:5173  <- 浏览器访问这个"
echo "  按 Ctrl+C 停止所有服务"
echo "============================================"
echo ""

wait
