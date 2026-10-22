$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath | Split-Path -Parent
$UiRoot = Join-Path $ProjectRoot "frontend\neuropulse-ui"
$UiDist = Join-Path $UiRoot "dist"
$DesktopUi = Join-Path $ProjectRoot "desktop\ui"

Push-Location $UiRoot
try {
    npm run build:desktop
    if ($LASTEXITCODE -ne 0) { throw "React desktop UI build failed." }
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Path $DesktopUi -Force | Out-Null
Copy-Item -Path (Join-Path $UiDist "*") -Destination $DesktopUi -Recurse -Force
Write-Host "Desktop UI prepared at $DesktopUi" -ForegroundColor Green
$BackendPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $BackendPython) {
    Write-Host "Local Python environment found. The desktop app will start its API automatically." -ForegroundColor Green
} else {
    Write-Host "Local Python environment not found. Python 3.11+ and backend\requirements.txt are needed for the API." -ForegroundColor Yellow
}
