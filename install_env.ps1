$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

Write-Host "=========================================" -ForegroundColor Green
Write-Host " S1/S2 Downloader - Env Setup " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""

try {
    $pythonVersion = & python --version
    Write-Host "Detected Python: $pythonVersion" -ForegroundColor Cyan
}
catch {
    Write-Host "Python was not found in PATH." -ForegroundColor Red
    Write-Host "Install Python 3.10+ first, and check 'Add Python to PATH'." -ForegroundColor Yellow
    exit 1
}

$venvPath = Join-Path $PSScriptRoot ".venv"

if (-not (Test-Path -LiteralPath $venvPath)) {
    Write-Host ""
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv $venvPath
}
else {
    Write-Host ""
    Write-Host "Virtual environment already exists." -ForegroundColor Cyan
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"

Write-Host ""
Write-Host "Upgrading pip..." -ForegroundColor Cyan
& $venvPython -m pip install --upgrade pip

Write-Host ""
Write-Host "Installing all project dependencies..." -ForegroundColor Cyan
& $venvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")

Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host " Setup Complete " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Run Sentinel-2 downloader:" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\python.exe -u .\S2download\S2_download.py" -ForegroundColor White
Write-Host ""
Write-Host "Run Sentinel-1 downloader:" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\python.exe -u .\S1download\S1_ASF_auto_download.py" -ForegroundColor White
