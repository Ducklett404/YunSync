$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
if (-not (Test-Path "frontend\node_modules")) {
    Push-Location frontend
    npm install
    Pop-Location
}

$backend = Start-Process -FilePath ".\.venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000" `
    -WorkingDirectory $Root -PassThru -WindowStyle Hidden

try {
    Push-Location frontend
    npm run dev -- --host 0.0.0.0 --port 5173
} finally {
    Pop-Location
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}

