# Sets up on first run, starts the Thatha TV web server in the background,
# then locks the PC into the full-screen remote. Use -NoKiosk to only start the server.
param([switch]$NoKiosk)
Set-Location $PSScriptRoot
$url = "http://localhost:8000"

if (-not (Test-Path .venv)) {
    python -m venv .venv
    .\.venv\Scripts\python -m pip install -r requirements.txt
}
if (-not (Test-Path .lgtv_client_key)) {
    Write-Host "No TV key found - pairing now. Accept the prompt on the TV."
    .\.venv\Scripts\python pair.py
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
    if (-not (ServerUp)) { Write-Host "Server did not start - see server.err.log"; exit 1 }
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.PrefixOrigin -eq 'Dhcp' } |
       Select-Object -First 1).IPAddress
Write-Host "Server running. Open http://${ip}:8000 on the iPad"

if (-not $NoKiosk) {
    Invoke-RestMethod "$url/kiosk/lock" -Method Post | Out-Null
    Start-Process powershell -WindowStyle Hidden `
        -ArgumentList "-ExecutionPolicy Bypass -NoProfile -File `"$PSScriptRoot\kiosk.ps1`""
}
