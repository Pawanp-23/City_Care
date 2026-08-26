# Starts CityCare in two visible PowerShell windows. Run from this repository:
#   powershell -ExecutionPolicy Bypass -File .\run-local.ps1
$root = $PSScriptRoot
$apiPython = Join-Path $root 'backend\.venv\Scripts\python.exe'

if (-not (Test-Path $apiPython)) {
    throw "Backend virtual environment is missing. Create it with: python -m venv backend\\.venv"
}

Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location '$root\backend'; & '$apiPython' -m uvicorn core.apis.api:app --host 0.0.0.0 --port 8000"
)

Start-Process powershell -ArgumentList @(
    '-NoExit', '-Command',
    "Set-Location '$root\frontend'; npm.cmd run dev -- --host 0.0.0.0"
)

Write-Host 'Started CityCare API on http://localhost:8000 and client on http://localhost:5173.'
Write-Host 'Keep both newly opened PowerShell windows open while using the app.'
