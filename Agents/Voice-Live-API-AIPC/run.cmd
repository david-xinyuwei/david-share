@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo 未找到虚拟环境，请先执行：
    echo     py -3 -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

if not exist ".env" (
    echo 未找到 .env，请先从 .env.example 复制并填写配置。
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" app.py
