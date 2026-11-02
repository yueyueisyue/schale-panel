@echo off
chcp 65001 >nul
setlocal
cd /d %~dp0backend

if not exist config.json (
  echo [setup] 未找到 config.json，从 config.example.json 复制一份
  copy config.example.json config.json >nul
  echo [setup] 请先编辑 backend\config.json，填好 data_dir 与 password
  pause
  exit /b 0
)

echo [1/2] 启动面板后端 ...
start "schale-panel" /min python main.py

echo [2/2] 等待端口就绪 ...
for /l %%i in (1,1,30) do (
  netstat -ano | findstr ":7870" | findstr LISTENING >nul && goto ready
  timeout /t 1 >nul
)

:ready
start "" http://127.0.0.1:7870/
echo 已打开 http://127.0.0.1:7870/
endlocal
