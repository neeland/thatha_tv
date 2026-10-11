# Sets up on first run, starts the Thatha TV web server in the background,
# then locks the PC into the full-screen remote. Use -NoKiosk to only start the server.
param([switch]$NoKiosk)
Set-Location $PSScriptRoot
$url = "http://127.0.0.1:8000"

# Run from the desktop icon the window closes on exit, so keep errors on screen until Enter
function Fail($msg) { Write-Host $msg -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

if (-not (Test-Path .venv\Scripts\python.exe)) {
    # Python is often installed but not on PATH (and "python" may be the Microsoft Store stub)
    $python = @(Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe",
                              "$env:ProgramFiles\Python3*\python.exe" -ErrorAction SilentlyContinue |
                Sort-Object FullName -Descending | Select-Object -ExpandProperty FullName) +
              @(Get-Command python -ErrorAction SilentlyContinue | Where-Object { $_.Source -notlike "*WindowsApps*" } |
                Select-Object -ExpandProperty Source) | Select-Object -First 1
    if (-not $python) {
        Fail "Python is not installed. Install Python 3.11+ from python.org, then try again."
    }
    & $python -m venv .venv
    .\.venv\Scripts\python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -Recurse -Force .venv
        Fail "Installing packages failed - check the internet connection and try again."
    }
}
if (-not (Test-Path .lgtv_client_key)) {
    Write-Host "No TV key found - pairing now. Turn the TV on and accept the prompt on the TV."
    .\.venv\Scripts\python pair.py
    if (-not (Test-Path .lgtv_client_key)) { Fail "Pairing failed. Make sure the TV is on, then try again." }
}
if (-not (Test-Path .unlock_pin)) {
    do { $pin = Read-Host "Choose a PIN (4-12 digits) to unlock the PC from the remote screen" }
    until ($pin -match '^\d{4,12}$')
    Set-Content .unlock_pin $pin
}

function ServerUp {
    try { Invoke-RestMethod "$url/status" -TimeoutSec 2 | Out-Null; $true } catch { $false }
}
if (-not (ServerUp)) {
    Start-Process .\.venv\Scripts\python.exe -ArgumentList "server.py" -WindowStyle Hidden `
        -RedirectStandardOutput server.log -RedirectStandardError server.err.log
    for ($i = 0; $i -lt 30 -and -not (ServerUp); $i++) { Start-Sleep 1 }
    if (-not (ServerUp)) { Fail "Server did not start - see server.err.log" }
}

Write-Host "Server running at $url"

if (-not $NoKiosk) {
    Invoke-RestMethod "$url/kiosk/lock" -Method Post | Out-Null
    Start-Process powershell -WindowStyle Hidden `
        -ArgumentList "-ExecutionPolicy Bypass -NoProfile -File `"$PSScriptRoot\kiosk.ps1`""
}
