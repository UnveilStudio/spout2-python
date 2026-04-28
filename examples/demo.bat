@echo off
REM demo.bat - one-click Spout sender-only demo for SPOUT2ForPython.
REM   Launches share_image.py which publishes assets\unveil_logo.png as a
REM   Spout source called "PythonImage" so any Spout-aware app on this
REM   machine can pick it up:
REM     - TouchDesigner: drop a "Spout In" TOP and pick "PythonImage"
REM     - OBS Studio:    add a "Spout2 Capture" source and pick "PythonImage"
REM     - Resolume / vMix / Notch: any Spout2 input pointed at "PythonImage"
REM
REM For an ALL-PYTHON demo (sender + cv2 preview window in one shot) use
REM examples\preview_local.bat instead.
REM
REM Press Ctrl+C in the sender window to stop.

setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

start "SPOUT2ForPython sender (PythonImage)" cmd /K "python ""%~dp0share_image.py"""

echo.
echo ============================================================
echo   SPOUT2ForPython demo - sender started
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
echo TIP: for an all-in-Python demo (sender + cv2 preview in one shot)
echo run examples\preview_local.bat instead.
echo ============================================================
echo.
pause
endlocal
