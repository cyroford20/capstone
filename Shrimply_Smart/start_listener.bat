@echo off
REM Shrimply Smart Serial Listener - Auto-start script
REM This keeps the listener running continuously

title Shrimply Smart Serial Listener
color 0A

:start
cd /d "C:\wamp64\www\Shrimply_Smart"
echo.
echo ========================================
echo Shrimply Smart Serial Listener
echo ========================================
echo Starting listener...
echo.

node serial_listener.js

echo.
echo Listener stopped. Restarting in 5 seconds...
timeout /t 5 /nobreak
goto start
