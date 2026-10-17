@echo off
setlocal
cd /d "%~dp0"
echo CYBER-TRAC local demo server
where python >nul 2>nul
if not errorlevel 1 goto use_python
where py >nul 2>nul
if not errorlevel 1 goto use_py_launcher
echo Python 3 was not found. Install Python 3 to start this local server.
pause
exit /b 1
:use_python
start "CYBER-TRAC browser" http://localhost:8000
python -m http.server 8000
goto end
:use_py_launcher
start "CYBER-TRAC browser" http://localhost:8000
py -3 -m http.server 8000
:end
