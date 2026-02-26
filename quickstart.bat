@echo off
setlocal
set "ROOT=D:\Codex\음성"
cd /d "%ROOT%"

if not exist .env (
  copy /Y .env.example .env > nul
)

if not exist .venv (
  python -m venv .venv
)

if not exist .venv\Scripts\activate.bat (
  echo [error] virtualenv가 준비되지 않았습니다. python이 설치되어 있는지 확인하세요.
  exit /b 1
)

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
