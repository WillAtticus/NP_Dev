# Run Streamlit dashboard
Write-Host "Starting NeuroPulse Streamlit Dashboard on http://127.0.0.1:8501" -ForegroundColor Magenta
Set-Location -Path (Split-Path -Parent $PSCommandPath)
$env:NEUROPULSE_BACKEND_URL = "http://127.0.0.1:8000"
streamlit run frontend/streamlit_app.py --server.port 8501 --server.address 127.0.0.1
