@echo off
setlocal
cd /d "%~dp0"

call "%~dp0Prepare Nova for Android.bat"
if errorlevel 1 exit /b 1

set "CMAKE_BUILD_PARALLEL_LEVEL=2"
call "%~dp0gradlew.bat" --no-daemon --max-workers=2 assembleDebug
if errorlevel 1 (
	echo.
	echo Install Android Studio and its Android SDK, NDK, and CMake components, then try again.
	pause
	exit /b 1
)

echo.
echo APK created at app\build\outputs\apk\debug\app-debug.apk
pause
