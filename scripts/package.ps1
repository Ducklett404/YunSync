param(
    [string]$Output = "release\YunSync-upload.zip"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))).Path
$OutputPath = [System.IO.Path]::GetFullPath((Join-Path $Root $Output))
$RootPrefix = $Root.TrimEnd('\') + '\'

if (-not $OutputPath.StartsWith($RootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Output must stay inside the project directory."
}

$OutputDirectory = Split-Path -Parent $OutputPath
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}

$excludedDirectories = @('.venv', 'node_modules', '__pycache__', '.pytest_cache', 'release', '.git')
$excludedFiles = @('.env')

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::Open($OutputPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem -LiteralPath $Root -File -Recurse | ForEach-Object {
        $relative = [System.IO.Path]::GetRelativePath($Root, $_.FullName)
        $parts = $relative -split '[\\/]'
        $isExcludedDirectory = $parts | Where-Object { $_ -in $excludedDirectories }
        $isExcludedFile = $_.Name -in $excludedFiles -or $_.Extension -in @('.db', '.pyc')

        if (-not $isExcludedDirectory -and -not $isExcludedFile) {
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $archive,
                $_.FullName,
                $relative.Replace('\', '/'),
                [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
        }
    }
} finally {
    $archive.Dispose()
}

Write-Host "Created $OutputPath" -ForegroundColor Green
