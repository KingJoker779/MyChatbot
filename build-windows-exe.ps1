$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputDirectory = Join-Path $projectRoot "Windows app"
$executable = Join-Path $outputDirectory "Nova.exe"
$workDirectory = Join-Path $env:TEMP "mychatbot-pyinstaller-build"
$uv = Get-Command uv -ErrorAction SilentlyContinue

if (-not $uv) {
	throw "Install uv first, or build with PyInstaller 6.22.3 and Python 3.14."
}

New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
$arguments = @(
	"run",
	"--python", "3.14",
	"--with", "pyinstaller==6.22.3",
	"pyinstaller",
	"--noconfirm",
	"--clean",
	"--onefile",
	"--console",
	"--name", "Nova",
	"--distpath", $outputDirectory,
	"--workpath", $workDirectory,
	"--specpath", $workDirectory,
	"--hidden-import", "setup_runtime",
	(Join-Path $projectRoot "project 1.py")
)

Push-Location $projectRoot
try {
	& $uv.Source @arguments
	if ($LASTEXITCODE -ne 0) {
		throw "PyInstaller failed with exit code $LASTEXITCODE."
	}
}
finally {
	Pop-Location
}

if (-not (Test-Path -LiteralPath $executable)) {
	throw "PyInstaller did not create $executable."
}

$size = (Get-Item -LiteralPath $executable).Length
if ($size -gt 100MB) {
	throw "The EXE is unexpectedly large ($([math]::Round($size / 1MB)) MB)."
}

Write-Host "Built $executable ($([math]::Round($size / 1MB, 1)) MB)."
Write-Host "The AI engine and model are downloaded separately on first launch."
