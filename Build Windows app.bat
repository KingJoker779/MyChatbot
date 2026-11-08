@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build-windows-exe.ps1"
if errorlevel 1 (
	echo.
	pause
	exit /b 1
)
echo.
echo The small EXE is in the "Windows app" folder.
pause
