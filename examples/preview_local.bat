@echo off
REM preview_local.bat - one-click full-Python demo (sender + cv2 preview).
REM   Launches preview_local.py which:
REM     1) Publishes a Spout source called "PythonPreview_<pid>" (visible
REM        from TouchDesigner/OBS/etc) animating the Unveil logo.
REM     2) Opens a local cv2 window showing the same frames, fed via
REM        Python multiprocessing.shared_memory (Spout's CPU-share path
REM        does not work between two Python instances - see README).
REM
REM Press 'q' in the preview window to close everything.

setlocal
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

python "%~dp0preview_local.py"

endlocal
