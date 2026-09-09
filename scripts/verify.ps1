$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

& ".\.venv\Scripts\python.exe" -m pytest
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }

& ".\.venv\Scripts\python.exe" -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }

& ".\.venv\Scripts\python.exe" -m alembic check
if ($LASTEXITCODE -ne 0) { throw "Database schema check failed." }

Push-Location frontend
try {
    npm run typecheck
    if ($LASTEXITCODE -ne 0) { throw "Frontend typecheck failed." }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally {
    Pop-Location
}

Write-Host "YunSync verification completed." -ForegroundColor Green
