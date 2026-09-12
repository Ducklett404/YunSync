$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

& ".\.venv\Scripts\python.exe" scripts/repository_security_scan.py
if ($LASTEXITCODE -ne 0) { throw "Repository secret scan failed." }

& ".\.venv\Scripts\python.exe" -m pip_audit -r requirements.txt --progress-spinner off
if ($LASTEXITCODE -ne 0) { throw "Python dependency audit failed." }

Push-Location frontend
try {
    npm audit --omit=dev --audit-level=high
    if ($LASTEXITCODE -ne 0) { throw "Frontend production dependency audit failed." }
} finally {
    Pop-Location
}

Write-Host "YunSync security audit completed." -ForegroundColor Green
