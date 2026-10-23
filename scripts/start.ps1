param([switch]$PrepareOnly)

# First-run setup and default launcher for the local NeuroPulse desktop app.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath | Split-Path -Parent
$DesktopRoot = Join-Path $ProjectRoot "desktop"
$FrontendRoot = Join-Path $ProjectRoot "frontend\neuropulse-ui"
$BackendPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$VenvRoot = Join-Path $ProjectRoot ".venv"
$Host.UI.RawUI.WindowTitle = "NeuroPulse Desktop"

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments, [string]$WorkingDirectory, [string]$FailureMessage)
    Push-Location $WorkingDirectory
    try {
        & $Executable @Arguments
        if ($LASTEXITCODE -ne 0) { throw $FailureMessage }
    } finally {
        Pop-Location
    }
}

$Npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $Npm) { throw "Node.js/npm is required. Install Node.js 20+ and open NeuroPulse again." }
$Node = Get-Command node -ErrorAction SilentlyContinue
if (-not $Node) { throw "Node.js was not found. Install Node.js 20+ and open NeuroPulse again." }
& $Node.Source -e "process.exit(Number(process.versions.node.split('.')[0]) >= 20 ? 0 : 1)"
if ($LASTEXITCODE -ne 0) { throw "NeuroPulse requires Node.js 20 or later. Update Node.js and open the app again." }

# Install the React build tools only when this checkout has not been set up yet.
if (-not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules\vite\bin\vite.js"))) {
    Write-Host "Preparing NeuroPulse interface dependencies (first launch)..." -ForegroundColor Yellow
    Invoke-Checked -Executable $Npm.Source -Arguments @("ci") -WorkingDirectory $FrontendRoot -FailureMessage "Could not install the interface dependencies. Connect to the internet, then open NeuroPulse again."
}

# Create a local Python environment on first launch when the repository has none.
if (-not (Test-Path -LiteralPath $BackendPython)) {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        & $PyLauncher.Source -3.11 -m venv $VenvRoot
    } else {
        $SystemPython = Get-Command python -ErrorAction SilentlyContinue
        if (-not $SystemPython) { throw "Python 3.11+ is required. Install it, then open NeuroPulse again." }
        & $SystemPython.Source -m venv $VenvRoot
    }
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $BackendPython)) {
        throw "Could not create NeuroPulse's local Python environment. Install Python 3.11+ and open the app again."
    }
}
& $BackendPython -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) { throw "NeuroPulse requires Python 3.11 or later. Install it and recreate the local .venv before launching." }

# Keep a small runtime dependency set in the app launcher; research/dev extras are not needed to run the API.
& $BackendPython -c "import fastapi, uvicorn, pydantic, sqlalchemy, alembic, numpy, scipy, h5py, serial, multipart"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Preparing the local NeuroPulse API (first launch)..." -ForegroundColor Yellow
    Invoke-Checked -Executable $BackendPython -Arguments @("-m", "pip", "install", "-r", "backend\requirements-runtime.txt") -WorkingDirectory $ProjectRoot -FailureMessage "Could not install the local API dependencies. Connect to the internet, then open NeuroPulse again."
}

# npm ci installs Electron itself and repairs a partial/missing Electron runtime.
$ElectronExecutable = Join-Path $DesktopRoot "node_modules\electron\dist\electron.exe"
if (-not (Test-Path -LiteralPath $ElectronExecutable)) {
    Write-Host "Preparing the NeuroPulse desktop runtime (first launch)..." -ForegroundColor Yellow
    Invoke-Checked -Executable $Npm.Source -Arguments @("ci") -WorkingDirectory $DesktopRoot -FailureMessage "Could not install Electron. Connect to the internet, then open NeuroPulse again."
}

$env:NEUROPULSE_PYTHON = $BackendPython
if ($PrepareOnly) {
    Write-Host "NeuroPulse startup dependencies are ready." -ForegroundColor Green
    exit 0
}
Push-Location $DesktopRoot
try {
    & $Npm.Source start
    if ($LASTEXITCODE -ne 0) { throw "NeuroPulse desktop app stopped with exit code $LASTEXITCODE." }
} finally {
    Pop-Location
}
