#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/backend"
if [ ! -f config.json ]; then
  cp config.example.json config.json
  echo "已生成 backend/config.json，请先编辑 data_dir 与 password 再运行"
  exit 0
fi
python main.py
