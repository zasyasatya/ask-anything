@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
title Ask Anything launcher

echo == Checking core dependencies ==
where python >nul 2>&1 || (echo [FAIL] Python not found - install Python 3.10+ & pause & exit /b 1)
for /f "tokens=*" %%v in ('python --version') do echo   [ OK ] %%v
where node >nul 2>&1 || (echo [FAIL] Node.js not found - install https://nodejs.org & pause & exit /b 1)
for /f "tokens=*" %%v in ('node --version') do echo   [ OK ] node %%v
where npm >nul 2>&1 || (echo [FAIL] npm not found & pause & exit /b 1)
for /f "tokens=*" %%v in ('npm --version') do echo   [ OK ] npm %%v

echo == Backend (FastAPI) ==
if not exist ".venv\Scripts\python.exe" (
    echo   creating virtualenv ...
    python -m venv .venv || (echo [FAIL] venv creation failed & pause & exit /b 1)
)
.venv\Scripts\python.exe -c "import fastapi, uvicorn, httpx, bs4" 2>nul
if errorlevel 1 (
    echo   installing backend requirements ...
    .venv\Scripts\python.exe -m pip install -r backend\requirements.txt || (echo [FAIL] pip install failed & pause & exit /b 1)
)
echo   [ OK ] backend dependencies available

echo == Frontend (Next.js) ==
if not exist "frontend\node_modules\next" (
    echo   npm install ...
    cd frontend && call npm install || (echo [FAIL] npm install failed & pause & exit /b 1)
    cd ..
)
echo   [ OK ] frontend dependencies available

if not exist data mkdir data
set ASK_DB_PATH=%cd%\data\ask_anything.db
if "%ASK_PROVIDER%"=="" set ASK_PROVIDER=huggingface

rem Optional: emulated local HF server when no llama-server is running
set BACKEND_URL=http://127.0.0.1:8000
powershell -Command "try { (Invoke-WebRequest -Uri http://127.0.0.1:8081/v1/models -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    if "%ASK_PROVIDER%"=="huggingface" (
        echo   [ !! ] no local LLM server on :8081 - starting emulated one (--demo)
        start "ask-llm-demo" /min .venv\Scripts\python.exe scripts\fake_llama_server.py
        timeout /t 3 /nobreak >nul
    )
)

echo == Starting backend and frontend ==
start "ask-backend" /min cmd /c ".venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 > data\backend.log 2>&1"
start "ask-frontend" /min cmd /c "cd frontend && npm run dev -- -p 3000 -H 0.0.0.0 > ..\data\frontend.log 2>&1"

echo.
echo ==============================================
echo   Ask Anything is starting
echo   UI   : http://localhost:3000
echo   API  : http://localhost:8000/api/health
echo   provider: %ASK_PROVIDER%
echo   Close the two console windows to stop.
echo ==============================================
timeout /t 5 /nobreak >nul
start "" http://localhost:3000
pause
