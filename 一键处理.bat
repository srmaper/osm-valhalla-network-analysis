@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\oneclick.ps1" %*
if errorlevel 1 (
  echo.
  echo 处理失败，请截图上面的错误信息。
)
pause
