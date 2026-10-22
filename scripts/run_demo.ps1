# NeuroPulse Standalone Demo Dashboard Launcher
# Kills any existing process on port 8501 before starting.
$Host.UI.RawUI.WindowTitle = "NeuroPulse Demo Dashboard"

$ProjectRoot = Split-Path -Parent $PSCommandPath | Split-Path -Parent
Set-Location -Path $ProjectRoot

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  NeuroPulse - Standalone Demo / Sandbox Dashboard" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Mode: Standalone (Signal Engine + NPI built-in)" -ForegroundColor Yellow
Write-Host "  URL:  http://127.0.0.1:8501" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# ── Kill any process already using port 8501 ──────────────────────────────
$port8501 = netstat -ano | Select-String ":8501 " | ForEach-Object {
    ($_ -split '\s+')[-1]
} | Select-Object -Unique
foreach ($pid in $port8501) {
    if ($pid -match '^\d+$' -and $pid -ne '0') {
        Write-Host "  Stopping existing process on port 8501 (PID $pid)..." -ForegroundColor DarkYellow
        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 1

# ── Run Streamlit setup ────────────────────────────────────────────────────
python scripts/setup_streamlit.py 2>$null

Write-Host "  Starting Streamlit..." -ForegroundColor Green
Write-Host ""

$env:NEUROPULSE_BACKEND_URL = "http://127.0.0.1:8000"
python -m streamlit run frontend/streamlit_app.py --server.port 8501 --server.address 127.0.0.1
