@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
	py -3 --version >nul 2>nul
	if not errorlevel 1 (
		set "PYTHON=py"
		set "PYTHON_ARGS=-3"
		goto python_ready
	)
)
where python >nul 2>nul
if not errorlevel 1 (
	python --version >nul 2>nul
	if not errorlevel 1 (
		set "PYTHON=python"
		set "PYTHON_ARGS="
		goto python_ready
	)
)
for %%P in ("%USERPROFILE%\.local\bin\python3*.exe") do if exist "%%~fP" (
	set "PYTHON=%%~fP"
	set "PYTHON_ARGS="
)
if defined PYTHON goto python_ready

echo Python 3 is required. Install it from https://www.python.org/downloads/
pause
exit /b 1

:python_ready
echo Downloading Nova's own AI engine and model. This needs internet and about 1 GB of storage.
"%PYTHON%" %PYTHON_ARGS% "%~dp0setup_runtime.py"
if errorlevel 1 (
	pause
	exit /b 1
)

echo Setup complete. Starting Nova.
set "NOVA_LAUNCHER=%~dp0Run Nova.bat"
set "NOVA_FOLDER=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell = New-Object -ComObject WScript.Shell; $shortcut = $shell.CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'Nova.lnk')); $shortcut.TargetPath = $env:NOVA_LAUNCHER; $shortcut.WorkingDirectory = $env:NOVA_FOLDER; $shortcut.Save()"
if errorlevel 1 echo Could not create the desktop shortcut. You can still open Run Nova.bat.
call "%~dp0Run Nova.bat"
