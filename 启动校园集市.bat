@echo off
chcp 65001 >nul
title 校园集市 Campus Market
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

"%PY%" launch.py
if errorlevel 1 pause
