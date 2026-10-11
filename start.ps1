# Sets up the venv on first run, then starts the Thatha TV web server.
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
    python -m venv .venv
    .\.venv\Scripts\python -m pip install -r requirements.txt
}
if (-not (Test-Path .lgtv_client_key)) {
    Write-Host "No TV key found - pairing now. Accept the prompt on the TV."
    .\.venv\Scripts\python pair.py
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.PrefixOrigin -eq 'Dhcp' } |
       Select-Object -First 1).IPAddress
Write-Host "Open http://${ip}:8000 on the iPad"
.\.venv\Scripts\python server.py
