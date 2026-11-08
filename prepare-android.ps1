$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$llamaRoot = Join-Path $projectRoot "llama.cpp"
$libraryProject = Join-Path $llamaRoot "examples\llama.android\lib\build.gradle.kts"
$wrapperJar = Join-Path $projectRoot "gradle\wrapper\gradle-wrapper.jar"
$sourceUrl = "https://codeload.github.com/ggml-org/llama.cpp/zip/refs/tags/b12193"
$wrapperUrl = "https://raw.githubusercontent.com/ggml-org/llama.cpp/b12193/examples/llama.android/gradle/wrapper/gradle-wrapper.jar"
$archive = Join-Path $projectRoot "llama.cpp-b12193.download.zip"
$extractRoot = Join-Path $projectRoot "llama.cpp-extracting"

try {
	if (-not (Test-Path -LiteralPath $libraryProject)) {
		if (Test-Path -LiteralPath $extractRoot) {
			Remove-Item -LiteralPath $extractRoot -Recurse -Force
		}
		if (Test-Path -LiteralPath $archive) {
			Remove-Item -LiteralPath $archive -Force
		}

		Write-Host "Downloading the official local AI engine source..."
		Invoke-WebRequest -Uri $sourceUrl -OutFile $archive -TimeoutSec 3600
		Expand-Archive -LiteralPath $archive -DestinationPath $extractRoot
		$sourceRoot = Join-Path $extractRoot "llama.cpp-b12193"
		$downloadedLibrary = Join-Path $sourceRoot "examples\llama.android\lib\build.gradle.kts"
		if (-not (Test-Path -LiteralPath $downloadedLibrary)) {
			throw "The Android AI engine source was incomplete."
		}
		Move-Item -LiteralPath $sourceRoot -Destination $llamaRoot
		Remove-Item -LiteralPath $extractRoot -Recurse -Force
		Remove-Item -LiteralPath $archive -Force
	}

	$downloadWrapper = -not (Test-Path -LiteralPath $wrapperJar)
	if (-not $downloadWrapper) {
		$existingWrapper = [System.IO.File]::ReadAllBytes($wrapperJar)
		$downloadWrapper = (
			$existingWrapper.Length -lt 50000 -or
			$existingWrapper[0] -ne 0x50 -or
			$existingWrapper[1] -ne 0x4B
		)
		if ($downloadWrapper) {
			Remove-Item -LiteralPath $wrapperJar -Force
		}
	}

	if ($downloadWrapper) {
		Write-Host "Downloading the Gradle launcher..."
		Invoke-WebRequest -Uri $wrapperUrl -OutFile $wrapperJar -TimeoutSec 60
		$downloadedWrapper = [System.IO.File]::ReadAllBytes($wrapperJar)
		if (
			$downloadedWrapper.Length -lt 50000 -or
			$downloadedWrapper[0] -ne 0x50 -or
			$downloadedWrapper[1] -ne 0x4B
		) {
			Remove-Item -LiteralPath $wrapperJar -Force
			throw "The Gradle launcher download was incomplete."
		}
	}

	Write-Host "Android project prepared."
	Write-Host "Open this folder in Android Studio: $projectRoot"
}
catch {
	Write-Error "Android setup failed: $_"
	exit 1
}
