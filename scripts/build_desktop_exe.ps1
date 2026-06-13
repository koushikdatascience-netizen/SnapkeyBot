$ErrorActionPreference = "Stop"

Set-Location (Split-Path $PSScriptRoot -Parent)

py -3.12 -m pip install -e ".[local-voice,connector,desktop]"
npm install
npm run build:live-agent

py -3.12 -m PyInstaller `
  --noconfirm `
  --clean `
  --name SnapkeyAssistant `
  --onedir `
  --collect-all faster_whisper `
  --collect-all uvicorn `
  --add-data "app\static;app\static" `
  desktop\snapkey_desktop.py

Write-Host ""
Write-Host "Desktop build created at dist\SnapkeyAssistant\SnapkeyAssistant.exe"
