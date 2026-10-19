# One-shot local stack: Ollama (0.0.0.0:11434) + Docker Compose
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\dev-up.ps1

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
Set-Location $repoRoot
Write-Host "[repo] $repoRoot"

# ---------- 1. Ollama ----------
$ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
if (-not $ollama) { $ollama = 'D:\ollama\ollama.exe' }
if (-not (Test-Path $ollama)) { throw "ollama.exe not found" }

$env:OLLAMA_HOST = '0.0.0.0:11434'

$listeners = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
$onAll = $listeners | Where-Object { $_.LocalAddress -in @('0.0.0.0', '::') }

if (-not $onAll) {
    if ($listeners) {
        Write-Host "[ollama] listening on loopback only, restarting..."
        Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Seconds 2
    }
    Write-Host "[ollama] starting on 0.0.0.0:11434 ..."
    Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden
    Start-Sleep -Seconds 4
}

$check = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in @('0.0.0.0', '::') }
if (-not $check) { throw "Ollama is not listening on 0.0.0.0:11434" }
Write-Host "[ollama] ready"

# ---------- 2. Docker Compose ----------
Write-Host "[docker] starting compose ..."
docker compose up -d

Write-Host ""
docker compose ps
Write-Host ""
Write-Host "frontend: http://127.0.0.1:5173"
Write-Host "backend : http://127.0.0.1:8000/api/v1/health"
