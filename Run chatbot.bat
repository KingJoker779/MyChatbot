@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
	py -3 --version >nul 2>nul
	if not errorlevel 1 (
		set "PYTHON=py"
		set "PYTHON_ARGS=-3"
		goto run
	)
)

where python >nul 2>nul
if not errorlevel 1 (
	python --version >nul 2>nul
	if not errorlevel 1 (
		set "PYTHON=python"
		set "PYTHON_ARGS="
		goto run
	)
)

for %%P in ("%USERPROFILE%\.local\bin\python3*.exe") do if exist "%%~fP" (
	set "PYTHON=%%~fP"
	set "PYTHON_ARGS="
)
if defined PYTHON goto run

echo Python 3 is required. Install it from https://www.python.org/downloads/
pause
exit /b 1

:run
"%PYTHON%" %PYTHON_ARGS% "%~dp0project 1.py"
if errorlevel 1 pause
