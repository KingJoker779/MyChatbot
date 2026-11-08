@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0prepare-android.ps1"
if errorlevel 1 (
	pause
	exit /b 1
)
echo.
echo Next, open this folder in Android Studio to build and install Nova.
pause
