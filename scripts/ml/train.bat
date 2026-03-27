@echo off
REM valtunox AI HR & cloudsystem Platform - Training CLI Launcher (Windows)
REM Usage: train.bat [command] [options]

set PYTHON_CMD=python
if exist "venv\Scripts\python.exe" (
    set PYTHON_CMD=venv\Scripts\python.exe
)
if exist "windows-venv\Scripts\python.exe" (
    set PYTHON_CMD=windows-venv\Scripts\python.exe
)

cd /d %~dp0..
%PYTHON_CMD% scripts\train_cli.py %*
