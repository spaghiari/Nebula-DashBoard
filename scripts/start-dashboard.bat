@echo off
title Claude Workspace Dashboard
echo.
echo  +======================================+
echo  ^|   Dashboard -- http://127.0.0.1:4777 ^|
echo  +======================================+
echo.
cd /d "%~dp0..\dashboard"
python server.py
pause
