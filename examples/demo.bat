@echo off
REM demo.bat - one-click Spout demo for spout2-python.
REM   Launches the share_image.py sender (which publishes assets\unveil_logo.png
REM   on the LAN as a Spout source called "PythonImage") plus the cv2 preview.
REM
REM NOTE on the cv2 preview: pure Python <-> Python loopback over Spout depends
REM on Windows GL/DX interop and is not always reliable. To CONFIRM the sender
REM is working, open one of these external receivers on the same machine:
REM   - TouchDesigner: drop a "Spout In" TOP and pick "PythonImage"
REM   - OBS Studio:    add a "Spout2 Capture" source and pick "PythonImage"
REM   - Resolume / vMix / Notch: any Spout2 input pointed at "PythonImage"
REM
REM Press Ctrl+C in either cmd window (or 'q' / ESC in the cv2 preview) to stop.

setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set REPO=%~dp0..

start "spout2-python sender" cmd /K "python ""%~dp0share_image.py"""
timeout /t 2 /nobreak >nul
start "spout2-python preview (cv2)" cmd /K "python ""%~dp0preview_example.py"""

echo.
echo Two windows opened: sender + preview.
echo The sender publishes the bundled Unveil logo as Spout source "PythonImage".
echo If the cv2 window stays black, open TouchDesigner / OBS to see it work.
endlocal
