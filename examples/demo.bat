@echo off
REM demo.bat - one-click Spout demo for spout2-python.
REM   Launches share_image.py which publishes assets\unveil_logo.png on the
REM   LAN as a Spout source called "PythonImage".
REM
REM IMPORTANT: pure-Python <-> pure-Python Spout loopback does NOT work
REM (Windows GL/DX interop is not exposed to ctypes / standalone GL contexts).
REM To VERIFY the sender is publishing, open one of these on the same machine:
REM   - TouchDesigner: drop a "Spout In" TOP and pick "PythonImage"
REM   - OBS Studio:    add a "Spout2 Capture" source and pick "PythonImage"
REM   - Resolume / vMix / Notch: any Spout2 input pointed at "PythonImage"
REM
REM Press Ctrl+C in the sender window to stop.

setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

start "spout2-python sender (PythonImage)" cmd /K "python ""%~dp0share_image.py"""

echo.
echo ============================================================
echo   spout2-python demo - sender started
echo ============================================================
echo.
echo The sender is publishing assets\unveil_logo.png as Spout
echo source "PythonImage" (loops at 30 fps until Ctrl+C).
echo.
echo To SEE it, open ANY Spout2 receiver on this machine:
echo   - TouchDesigner: Spout In TOP -^> select "PythonImage"
echo   - OBS Studio:    Source "Spout2 Capture" -^> "PythonImage"
echo   - Resolume / vMix / Notch / ...
echo.
echo Why no Python preview window? Pure-Python receivers cannot
echo open the GL/DX shared texture (a known SpoutLibrary limitation).
echo See README "Known limitations" for details.
echo ============================================================
echo.
pause
endlocal
