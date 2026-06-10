@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

if "%PORT%"=="" set "PORT=5001"
if "%HOST%"=="" set "HOST=0.0.0.0"
set "PYTHON_EXE=..\.venv\Scripts\python.exe"

echo ================================================
echo   标小易 model - Windows 内网启动
echo ================================================
echo.

if not exist "%PYTHON_EXE%" (
  echo [错误] 找不到虚拟环境 Python:
  echo        %CD%\%PYTHON_EXE%
  echo.
  echo 请先在 model 目录执行:
  echo   py -3.12 -m venv .venv
  echo   .\.venv\Scripts\Activate.ps1
  echo   pip install -r openai-rfp-response-analyzer\requirements.txt
  echo.
  pause
  exit /b 1
)

echo [1/3] 尝试添加 Windows 防火墙入站规则，端口 %PORT%
netsh advfirewall firewall add rule name="Biaoxiaoyi Model %PORT%" dir=in action=allow protocol=TCP localport=%PORT% >nul 2>nul
if %errorlevel% neq 0 (
  echo      未能自动添加防火墙规则。请用管理员身份运行本脚本，或手动放行 TCP %PORT%。
) else (
  echo      已添加或刷新防火墙规则。
)

echo.
echo [2/3] 本机内网 IPv4 地址:
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.AddressState -eq 'Preferred' } | ForEach-Object { '      http://' + $_.IPAddress + ':%PORT%' }"

echo.
echo [3/3] 启动服务
echo      本机访问: http://127.0.0.1:%PORT%
echo      内网访问: http://本机IPv4:%PORT%
echo.

"%PYTHON_EXE%" main.py

echo.
echo 服务已退出。
pause

