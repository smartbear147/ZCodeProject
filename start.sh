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

# ---------- 前置检查 ----------
if ! command -v python3 &>/dev/null; then
  echo "[错误] 未找到 python3，请先安装 Python 3.11+"
  exit 1
fi
if ! command -v node &>/dev/null; then
  echo "[错误] 未找到 node，请先安装 Node.js"
  exit 1
fi

# ---------- .env 检查 ----------
cd backend
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "[后端] 已从 .env.example 创建 .env，请编辑 backend/.env 填入你的 API 密钥后再重启。"
    exit 1
  fi
fi
cd ..

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
echo "  面试助手 - 已启动"
echo "============================================"
echo "  后端: http://localhost:8000  (健康检查 /health)"
echo "  前端: http://localhost:5173  <- 浏览器访问这个"
echo "  按 Ctrl+C 停止所有服务"
echo "============================================"
echo ""

wait