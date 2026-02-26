@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
if exist "%ROOT%release\voice-cli-agent-dir-2\voice-cli-agent-dir.exe" (
  set "EXE=%ROOT%release\voice-cli-agent-dir-2\voice-cli-agent-dir.exe"
) else if exist "%ROOT%release\voice-cli-agent-dir\voice-cli-agent-dir.exe" (
  set "EXE=%ROOT%release\voice-cli-agent-dir\voice-cli-agent-dir.exe"
) else (
  set "EXE="
)

if not exist "%EXE%" (
  echo [error] onedir executable not found.
  echo path: %ROOT%release\voice-cli-agent-dir\voice-cli-agent-dir.exe
  pause
  exit /b 1
)

:menu
echo ===========================
echo  Voice CLI Agent (onedir)
echo ===========================
echo.
echo  1. Voice mode (microphone)
echo  2. Text mode (--text)
echo  3. Exit
set /P "CHOICE=Select [1/2/3]: "

echo.

if "%CHOICE%"=="1" (
  "%EXE%"
  goto menu
)
if "%CHOICE%"=="2" (
  "%EXE%" --text
  goto menu
)
if "%CHOICE%"=="3" exit /b 0
if /I "%CHOICE%"=="q" exit /b 0

echo [warn] Enter 1, 2, or 3.
pause
goto menu

:done
echo [done] Process finished.
pause
exit /b 0
