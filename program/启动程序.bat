@echo off
chcp 65001 >nul
title WHITE ALBUM 2 - 冬马和纱（开发运行）
cd /d "%~dp0"
"%~dp0build_env\venv\Scripts\python.exe" "%~dp0tools\run_dev.py"
