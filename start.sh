#!/usr/bin/env bash
# SCHALE Panel 启动脚本（macOS / Linux）
set -e
cd "$(dirname "$0")"

PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "没找到 python3，请先安装 Python 3.10+"
  exit 1
fi

echo "[1/3] $($PY -V 2>&1)"

if ! $PY -c "import fastapi, uvicorn, httpx" >/dev/null 2>&1; then
  echo "[2/3] 安装依赖 ..."
  $PY -m pip install -r backend/requirements.txt
else
  echo "[2/3] 依赖已就绪"
fi

if [ ! -f backend/config.json ]; then
  cp backend/config.example.json backend/config.json
  echo "[3/3] 已生成 backend/config.json"
  echo "      先填好 data_dir 与 password，保存后再运行一次本脚本。"
  echo "      编辑器示例：nano backend/config.json"
  exit 0
fi

echo "[3/3] 启动面板 → http://127.0.0.1:7870/"
cd backend
exec $PY main.py
