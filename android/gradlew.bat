@echo off
setlocal
set "APP_HOME=%~dp0"

if defined JAVA_HOME (
	set "JAVA_EXE=%JAVA_HOME%\bin\java.exe"
) else (
	if exist "%ProgramFiles%\Android\Android Studio\jbr\bin\java.exe" (
		set "JAVA_EXE=%ProgramFiles%\Android\Android Studio\jbr\bin\java.exe"
	) else if exist "%LOCALAPPDATA%\Programs\Android Studio\jbr\bin\java.exe" (
		set "JAVA_EXE=%LOCALAPPDATA%\Programs\Android Studio\jbr\bin\java.exe"
	) else (
		for %%J in (java.exe) do set "JAVA_EXE=%%~$PATH:J"
	)
)

if not defined JAVA_EXE (
	echo Java was not found. Install Android Studio, then try again.
	exit /b 1
)

"%JAVA_EXE%" -classpath "%APP_HOME%gradle\wrapper\gradle-wrapper.jar" org.gradle.wrapper.GradleWrapperMain %*
