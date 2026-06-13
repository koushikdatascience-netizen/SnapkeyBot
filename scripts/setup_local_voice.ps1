$ErrorActionPreference = "Stop"

Set-Location (Split-Path $PSScriptRoot -Parent)

py -3.12 -m pip install -e ".[local-voice,connector,dev]"
npm install
npm run build:live-agent

Write-Host ""
Write-Host "Local voice dependencies installed."
Write-Host "Set LOCAL_VOICE_ENABLED=true in .env, then run:"
Write-Host "  py -3.12 desktop\snapkey_desktop.py"
