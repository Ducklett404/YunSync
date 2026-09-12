param(
    [string]$BaseUrl = "http://127.0.0.1:8000/start",
    [string]$ExpectedText = "登录并确认使用边界"
)

$ErrorActionPreference = "Stop"

if (-not [Uri]::IsWellFormedUriString($BaseUrl, [UriKind]::Absolute)) {
    throw "BaseUrl must be an absolute URL."
}

$edgeCandidates = @(
    "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
)
$edgePath = $edgeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $edgePath) {
    throw "Microsoft Edge is not installed in a supported location."
}

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("yunsync-browser-smoke-" + [Guid]::NewGuid().ToString("N"))
$null = New-Item -ItemType Directory -Path $tempRoot
$viewports = @(
    @{ Name = "desktop"; Width = 1440; Height = 900 },
    @{ Name = "tablet"; Width = 1024; Height = 768 },
    @{ Name = "mobile"; Width = 390; Height = 844 }
)

try {
    foreach ($viewport in $viewports) {
        $profilePath = Join-Path $tempRoot ("profile-" + $viewport.Name)
        $domPath = Join-Path $tempRoot ($viewport.Name + ".html")
        $errorPath = Join-Path $tempRoot ($viewport.Name + ".stderr.log")
        $screenshotPath = Join-Path $tempRoot ($viewport.Name + ".png")
        $arguments = @(
            "--headless=new",
            "--disable-gpu",
            "--disable-extensions",
            "--no-first-run",
            "--user-data-dir=$profilePath",
            "--window-size=$($viewport.Width),$($viewport.Height)",
            "--virtual-time-budget=5000",
            "--screenshot=$screenshotPath",
            "--dump-dom",
            $BaseUrl
        )
        $process = Start-Process -FilePath $edgePath -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput $domPath -RedirectStandardError $errorPath
        if ($process.ExitCode -ne 0) {
            throw "Edge $($viewport.Name) smoke failed with exit code $($process.ExitCode)."
        }
        $dom = Get-Content -Raw -LiteralPath $domPath
        if (-not $dom.Contains('id="app"') -or -not $dom.Contains($ExpectedText)) {
            throw "Edge $($viewport.Name) smoke did not render the expected surface."
        }
        if (-not (Test-Path -LiteralPath $screenshotPath)) {
            throw "Edge $($viewport.Name) smoke did not produce a screenshot."
        }
        Write-Output "PASS edge/$($viewport.Name) $($viewport.Width)x$($viewport.Height)"
    }
} finally {
    $resolvedTemp = [IO.Path]::GetFullPath($tempRoot)
    $expectedPrefix = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolvedTemp.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedTemp)) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}

exit 0
