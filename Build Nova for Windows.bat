@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-nova-windows.ps1"
if errorlevel 1 (
	echo.
	pause
	exit /b 1
)
echo.
echo The small EXE is in the "Nova for Windows" folder.
pause
