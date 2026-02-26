$root = 'D:\Codex\음성'
Set-Location -Path $root

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}

if (-not (Test-Path .venv)) {
    python -m venv .venv
}

if (-not (Test-Path .venv\Scripts\Activate.ps1)) {
    Write-Error '.\.venv\Scripts\Activate.ps1 not found. Check Python install.'
    exit 1
}

& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe app.py
