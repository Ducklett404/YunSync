param(
    [string]$Output = "release\YunSync-V2.0.zip",
    [string]$Version = "V2.0"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

& $Python (Join-Path $PSScriptRoot "build_release_package.py") --output $Output --version $Version
if ($LASTEXITCODE -ne 0) {
    throw "Release package build failed with exit code $LASTEXITCODE."
}
