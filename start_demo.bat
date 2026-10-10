@echo off
setlocal
cd /d "%~dp0"
py scripts\start_demo.py %*
if errorlevel 1 exit /b %errorlevel%
