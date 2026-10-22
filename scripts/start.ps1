# Default launcher: open NeuroPulse in its Windows desktop window.
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSCommandPath | Split-Path -Parent
$DesktopRoot = Join-Path $ProjectRoot "desktop"
$Host.UI.RawUI.WindowTitle = "NeuroPulse Desktop"

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js/npm is required. Install the project dependencies described in README.md first."
}

Push-Location $DesktopRoot
try {
    $ElectronExecutable = Join-Path $DesktopRoot "node_modules\electron\dist\electron.exe"
    if (-not (Test-Path -LiteralPath $ElectronExecutable)) {
        Write-Host "NeuroPulse needs its local Electron runtime. Trying to download it now..." -ForegroundColor Yellow
        npm exec -- install-electron --no
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $ElectronExecutable)) {
            throw "Could not download Electron runtime. Check this computer's internet access to the official Electron release host, then open NeuroPulse again."
        }
    }
    npm start
    if ($LASTEXITCODE -ne 0) {
        throw "NeuroPulse desktop app stopped with exit code $LASTEXITCODE."
    }
} finally {
    Pop-Location
}
