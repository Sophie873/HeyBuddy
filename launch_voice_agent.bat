@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "ONEFILE=%ROOT%release\voice-cli-agent.exe"
set "ONEDIR=%ROOT%release\voice-cli-agent-dir\voice-cli-agent-dir.exe"
if exist "%ROOT%release\voice-cli-agent-dir-2\voice-cli-agent-dir.exe" set "ONEDIR=%ROOT%release\voice-cli-agent-dir-2\voice-cli-agent-dir.exe"

if not exist "%ONEDIR%" (
  if not exist "%ONEFILE%" (
    echo [error] No executable found in the release folder.
    echo Run build_exe.ps1 first, then run this launcher again.
    pause
    exit /b 1
  )
)

:menu
echo ===========================
echo  Voice CLI Agent Launcher
echo ===========================
echo.
echo  1. Start voice mode (microphone)
echo  2. Start text mode (--text)
echo  3. Exit
echo.
set "CHOICE="
set /P "CHOICE=Select [1/2/3]: "

if "%CHOICE%"=="1" (
  call :RUN_VOICE
  goto menu
)
if "%CHOICE%"=="2" (
  call :RUN_TEXT
  goto menu
)
if "%CHOICE%"=="3" exit /b 0
if /I "%CHOICE%"=="q" exit /b 0

echo [warn] Press 1, 2, 3 or q.
pause

goto menu

:RUN_VOICE
call :RUN_AGENT ""
goto :eof

:RUN_TEXT
call :RUN_AGENT "--text"
goto :eof

:RUN_AGENT
set "ARGS=%~1"
set "EXE="
if exist "%ONEDIR%" set "EXE=%ONEDIR%"
if not defined EXE if exist "%ONEFILE%" set "EXE=%ONEFILE%"

if not defined EXE (
  echo [error] Cannot locate executable path.
  pause
  goto :eof
)

cd /d "%ROOT%release"
if /I "%EXE%"=="%ONEDIR%" (
  echo [info] Running onedir mode...
) else (
  echo [info] Running one-file mode...
)

if "%ARGS%"=="" (
  "%EXE%"
) else (
  "%EXE%" %ARGS%
)
set "CODE=%errorlevel%"

if not "%CODE%"=="0" (
  echo.
  echo [warn] Exit code: %CODE%
  if /I "%EXE%"=="%ONEFILE%" if exist "%ONEDIR%" (
    echo [info] One-file failed. Trying onedir fallback automatically.
    "%ONEDIR%" %ARGS%
    set "CODE=%errorlevel%"
  )
)

if "%CODE%"=="0" (
  echo [done] Process ended.
) else (
  echo [warn] Abnormal end.
)
pause
set "CODE="
goto :eof
