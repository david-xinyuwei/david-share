@echo off
if "%AIPC_APP_DIR%"=="" set "AIPC_APP_DIR=%USERPROFILE%\Desktop"
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=python.exe"
cd /d "%AIPC_APP_DIR%"
"%PYTHON_EXE%" sandbox_api.py >> sandbox_api.log 2>&1
