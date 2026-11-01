@echo off
chcp 65001 >nul
title 校园集市 - 公网分享
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

"%PY%" share.py
if errorlevel 1 pause
