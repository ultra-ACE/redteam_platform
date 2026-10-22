# One-shot local rebuild: Ollama + PostgreSQL/Redis + latest migrations + images
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

$ollamaReady = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in @('0.0.0.0', '::') }
if (-not $ollamaReady) { throw "Ollama is not listening on 0.0.0.0:11434" }
Write-Host "[ollama] ready"

# ---------- 2. Database dependencies ----------
Write-Host "[docker] starting postgres and redis ..."
docker compose up -d postgres redis
if ($LASTEXITCODE -ne 0) { throw "failed to start postgres/redis" }

$deadline = (Get-Date).AddSeconds(60)
do {
    $dbStatus = docker inspect -f '{{.State.Health.Status}}' llm-eval-postgres 2>$null
    if ($dbStatus -eq 'healthy') { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
if ($dbStatus -ne 'healthy') { throw "postgres did not become healthy" }
Write-Host "[docker] postgres healthy"

# ---------- 3. Backup before destructive migrations ----------
$backupDir = Join-Path $repoRoot 'backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$dumpName = "llm_eval_$timestamp.dump"
$containerDump = "/tmp/$dumpName"

Write-Host "[backup] dumping database to backups\$dumpName ..."
docker exec llm-eval-postgres pg_dump -U llm_eval -d llm_eval -Fc -f $containerDump
if ($LASTEXITCODE -ne 0) { throw "database backup failed; migration aborted" }
docker cp "llm-eval-postgres:$containerDump" (Join-Path $backupDir $dumpName)
if ($LASTEXITCODE -ne 0) { throw "failed to copy database backup to host" }
docker exec llm-eval-postgres rm -f $containerDump | Out-Null
Write-Host "[backup] ready: backups\$dumpName"

# ---------- 4. Rebuild and migrate ----------
Write-Host "[docker] building latest backend and frontend images ..."
docker compose build api frontend
if ($LASTEXITCODE -ne 0) { throw "docker build failed" }

Write-Host "[docker] applying latest migrations ..."
docker compose run --rm migrate
if ($LASTEXITCODE -ne 0) { throw "database migration failed" }

Write-Host "[docker] starting api, worker and frontend ..."
docker compose up -d api worker frontend
if ($LASTEXITCODE -ne 0) { throw "failed to start application services" }

# ---------- 5. Health check ----------
$deadline = (Get-Date).AddSeconds(90)
$healthOk = $false
do {
    try {
        $response = Invoke-WebRequest -UseBasicParsing `
            -Uri 'http://127.0.0.1:8000/api/v1/health' `
            -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            $healthOk = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 2
    }
} while ((Get-Date) -lt $deadline)
if (-not $healthOk) { throw "API health check did not become healthy" }

Write-Host ""
docker compose ps
Write-Host ""
Write-Host "frontend: http://127.0.0.1:5173"
Write-Host "backend : http://127.0.0.1:8000/api/v1/health"
