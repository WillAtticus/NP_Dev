# NeuroPulse Full Stack Launcher
# Kills existing processes on ports 8000 and 8501 before starting.
$Host.UI.RawUI.WindowTitle = "NeuroPulse Full Stack"

$ProjectRoot = Split-Path -Parent $PSCommandPath | Split-Path -Parent
Set-Location -Path $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  NeuroPulse - Full Stack Launcher" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# ── Helper: kill process on a given port ──────────────────────────────────
function Kill-Port {
    param([int]$Port)
    $pids = netstat -ano | Select-String ":$Port " | ForEach-Object {
        ($_ -split '\s+')[-1]
    } | Select-Object -Unique
    foreach ($p in $pids) {
        if ($p -match '^\d+$' -and $p -ne '0') {
            Write-Host "  Stopping process on port $Port (PID $p)..." -ForegroundColor DarkYellow
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "[0/3] Freeing ports 8000 and 8501..." -ForegroundColor DarkGray
Kill-Port 8000
Kill-Port 8501
Start-Sleep -Seconds 1

# ── Start FastAPI backend in a separate window ─────────────────────────────
Write-Host "[1/3] Starting FastAPI backend on http://127.0.0.1:8000 ..." -ForegroundColor Yellow
Start-Process powershell.exe -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ProjectRoot'; `$Host.UI.RawUI.WindowTitle='NeuroPulse Backend'; python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
)

# ── Wait for backend to be ready ──────────────────────────────────────────
Write-Host "[2/3] Waiting for backend to start (3s)..." -ForegroundColor DarkGray
Start-Sleep -Seconds 3

# ── Run Streamlit setup ────────────────────────────────────────────────────
python scripts/setup_streamlit.py 2>$null

# ── Start Streamlit dashboard in this window ───────────────────────────────
Write-Host "[3/3] Starting Streamlit Dashboard on http://127.0.0.1:8501 ..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Dashboard  -> http://127.0.0.1:8501" -ForegroundColor Cyan
Write-Host "  API Docs   -> http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host "  Health     -> http://127.0.0.1:8000/api/v1/health" -ForegroundColor Cyan
Write-Host ""

$env:NEUROPULSE_BACKEND_URL = "http://127.0.0.1:8000"
python -m streamlit run frontend/streamlit_app.py --server.port 8501 --server.address 127.0.0.1
