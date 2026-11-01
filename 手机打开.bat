@echo off
chcp 65001 >nul
title 校园集市 - 手机同 Wi-Fi 打开
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

"%PY%" launch.py --lan
if errorlevel 1 pause
