<#
.SYNOPSIS
    Build the Windows folder of the page, the server and the analysis. FR-106.

.DESCRIPTION
    Produces `packaging/dist/MultibandHall/MultibandHall.exe` and a zip of that
    folder for sending.

    Builds the frontend first unless -SkipFrontend is given. `app/static/` is
    generated and not in the repository, so a build that skipped it would ship
    whatever was left from last time, or a server with no page.

.EXAMPLE
    .\packaging\build.ps1
    .\packaging\build.ps1 -SkipFrontend
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    Write-Error "No virtual environment at $python`nRun:  python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-app.txt"
}
& $python -c "import PyInstaller, fastapi, uvicorn, multipart" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "The packaging dependencies are missing.`nRun:  .\.venv\Scripts\python.exe -m pip install -r requirements-app.txt"
}

if (-not $SkipFrontend) {
    Write-Host 'Building the frontend...' -ForegroundColor Cyan
    Push-Location (Join-Path $root 'frontend')
    try {
        if (-not (Test-Path 'node_modules')) {
            npm install --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { Write-Error 'npm install failed.' }
        }
        npm run build
        if ($LASTEXITCODE -ne 0) { Write-Error 'Frontend build failed.' }
    } finally { Pop-Location }
}

$index = Join-Path $root 'app\static\index.html'
if (-not (Test-Path $index)) {
    Write-Error "No built frontend at $index`nRun without -SkipFrontend, or:  cd frontend; npm run build"
}

Write-Host 'Freezing...' -ForegroundColor Cyan
Push-Location $PSScriptRoot
try {
    & $python -m PyInstaller --noconfirm --clean --distpath dist --workpath build MultibandHall.spec
    if ($LASTEXITCODE -ne 0) { Write-Error 'PyInstaller failed.' }
} finally { Pop-Location }

$folder = Join-Path $PSScriptRoot 'dist\MultibandHall'
$exe = Join-Path $folder 'MultibandHall.exe'
if (-not (Test-Path $exe)) { Write-Error "Expected $exe, which is not there." }

$zip = Join-Path $PSScriptRoot 'dist\MultibandHall-windows.zip'
Write-Host 'Compressing...' -ForegroundColor Cyan
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path $folder -DestinationPath $zip
$folderMb = (Get-ChildItem $folder -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
$zipMb = (Get-Item $zip).Length / 1MB
Write-Host ''
Write-Host ("  {0}" -f $exe) -ForegroundColor Green
Write-Host ("  folder {0:N0} MB, zip {1:N0} MB. Unzip, then run MultibandHall\MultibandHall.exe" -f $folderMb, $zipMb) -ForegroundColor Green
Write-Host ''
Write-Host '  Verified here only that it builds and runs on this machine, which has' -ForegroundColor DarkGray
Write-Host '  Python installed. Whether it runs where Python is absent is answered by' -ForegroundColor DarkGray
Write-Host '  copying it to such a machine and opening it.' -ForegroundColor DarkGray
