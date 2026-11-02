@echo off
chcp 936 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title SCHALE Panel
set "LOG=%~dp0panel.log"

echo ============================================================
echo   SCHALE Panel - 碧蓝档案风格 AstrBot 面板
echo ============================================================
echo.

REM ---- 1. 找一个能用的 Python (3.10 以上) ----
set "PY="
for %%C in ("py -3" "python" "python3") do (
  if not defined PY (
    %%~C -c "import sys;raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=%%~C"
  )
)
if not defined PY (
  for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
    if not defined PY (
      if exist "%%D\python.exe" "%%D\python.exe" -c "import sys;raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=%%D\python.exe"
    )
  )
)
if not defined PY (
  for /d %%D in ("C:\Python3*") do (
    if not defined PY (
      if exist "%%D\python.exe" "%%D\python.exe" -c "import sys;raise SystemExit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul && set "PY=%%D\python.exe"
    )
  )
)
if not defined PY (
  echo [x] 没有找到可用�?Python 3.10 以上版本�?  echo.
  echo     1. 打开 https://www.python.org/downloads/ 下最新版
  echo     2. 安装第一屏务必勾�?"Add python.exe to PATH"
  echo     3. 装完重启这个 start.bat
  echo.
  echo     如果你装�?Microsoft Store 里的 python，那只是个空壳：
  echo     系统设置 - 应用 - 高级应用设置 - 应用执行别名�?  echo     �?python.exe �?python3.exe 两项关掉，再重装 Python�?  echo.
  pause
  exit /b 1
)
echo [1/4] Python 就绪

REM ---- 2. 依赖 ----
%PY% -c "import fastapi, uvicorn, httpx" >nul 2>nul
if errorlevel 1 (
  echo [2/4] 装依赖，第一次要等一两分�?...
  %PY% -m pip install --upgrade pip >nul 2>nul
  %PY% -m pip install -r backend\requirements.txt
  %PY% -c "import fastapi, uvicorn, httpx" >nul 2>nul
  if errorlevel 1 (
    echo.
    echo [x] 依赖没装上，多半是网络问题，换国内镜像再来一次：
    echo     %PY% -m pip install -r backend\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause
    exit /b 1
  )
) else (
  echo [2/4] 依赖已就�?)

REM ---- 3. 配置 ----
set "CFG=backend\config.json"
if not exist "%CFG%" (
  echo [3/4] 第一次运行，生成 backend\config.json
  copy /y backend\config.example.json "%CFG%" >nul
  echo.
  echo ------------------------------------------------------------
  echo  马上弹出记事本，填这 3 项，保存后关掉记事本就会继续�?  echo    data_dir   AstrBot �?data 目录，例�?D:/AstrBot/data
  echo    password   面板登录密码，现在是 CHANGE_ME，一定要�?  echo    onebot     只有要从面板�?QQ 消息时才需要填
  echo ------------------------------------------------------------
  echo.
  start /wait notepad "%CFG%"
) else (
  echo [3/4] 用已有的 backend\config.json
)

REM ---- 4. 启动（输出写�?panel.log，出错好排查�?----
echo [4/4] 启动面板 ... 这个窗口别关，关掉服务就停了
echo.
if exist "%LOG%" del /q "%LOG%"
pushd backend
start "" /b cmd /c "%PY% main.py > "%LOG%" 2>&1"
popd

set /a N=0
:wait
netstat -ano | findstr /c:":7870" | findstr /i "LISTENING" >nul 2>nul
if not errorlevel 1 goto ready
set /a N+=1
if !N! GEQ 40 goto timeout
ping -n 2 127.0.0.1 >nul
goto wait

:ready
echo.
echo   面板就绪 :- http://127.0.0.1:7870/
echo   登录密码就是 backend\config.json 里的 password
echo.
call :openbrowser "http://127.0.0.1:7870/"
goto hold

:timeout
echo.
echo [x] 等了 40 秒服务还没起来。下面是后端最后几行输出：
echo ------------------------------------------------------------
if exist "%LOG%" (
  powershell -NoProfile -Command "Get-Content -LiteralPath '%LOG%' -Tail 20" 2>nul
) else (
  echo 没有生成 panel.log，说�?python 可能根本没跑起来�?)
echo ------------------------------------------------------------
echo  常见原因�?echo    1. config.json 里的 data_dir 路径写错（用正斜杠，例如 D:/AstrBot/data�?echo    2. 编辑 config.json 时留下了中文标点或不必要的逗号
echo    3. 7870 端口被别的程序占了：netstat -ano ^| findstr :7870
echo.

:hold
echo.
echo 按任意键关闭这个窗口，面板服务会一起停�?pause >nul
exit /b 0

:openbrowser
start "" %1
if errorlevel 1 rundll32 url.dll,FileProtocolHandler %1
if not errorlevel 1 exit /b 0
explorer %1
exit /b 0
