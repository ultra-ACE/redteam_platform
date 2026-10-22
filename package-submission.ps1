$ErrorActionPreference = 'Stop'

$root = $PSScriptRoot
$releaseDir = Join-Path $root 'release'
$stageDir = Join-Path $releaseDir 'redteam_platform'
$zipPath = Join-Path $releaseDir 'redteam_platform_source.zip'

if (-not (Test-Path $releaseDir)) {
    New-Item -ItemType Directory -Path $releaseDir -Force | Out-Null
}
if (Test-Path $stageDir) {
    $resolvedStage = (Resolve-Path $stageDir).Path
    $resolvedRelease = (Resolve-Path $releaseDir).Path
    if (-not $resolvedStage.StartsWith($resolvedRelease, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove staging directory outside release/"
    }
    Remove-Item -LiteralPath $resolvedStage -Recurse -Force
}
if (Test-Path $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}
New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

$rootFiles = @(
    'README.md',
    'README_DEPLOY.md',
    'docker-compose.yml',
    'dev-up.ps1',
    'openapi.yaml'
)

foreach ($file in $rootFiles) {
    Copy-Item -LiteralPath (Join-Path $root $file) -Destination (Join-Path $stageDir $file)
}

function Copy-Tree {
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$ExcludeDirectories,
        [string[]]$ExcludeFiles
    )

    $arguments = @($Source, $Destination, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP')
    if ($ExcludeDirectories.Count -gt 0) {
        $arguments += '/XD'
        $arguments += $ExcludeDirectories
    }
    if ($ExcludeFiles.Count -gt 0) {
        $arguments += '/XF'
        $arguments += $ExcludeFiles
    }

    robocopy @arguments | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed for $Source with exit code $LASTEXITCODE"
    }
}

Copy-Tree `
    -Source (Join-Path $root 'backend') `
    -Destination (Join-Path $stageDir 'backend') `
    -ExcludeDirectories @('.venv', '__pycache__', '.pytest_cache', 'data', 'backups') `
    -ExcludeFiles @('*.pyc', '*.pyo', '*.log', '.env')

Copy-Tree `
    -Source (Join-Path $root 'frontend') `
    -Destination (Join-Path $stageDir 'frontend') `
    -ExcludeDirectories @('node_modules', 'dist', '.npm-cache', '.vite') `
    -ExcludeFiles @('.env', '*.log')

Compress-Archive -LiteralPath $stageDir -DestinationPath $zipPath -CompressionLevel Optimal

$sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 2)
Write-Host "submission=$zipPath"
Write-Host "size_mb=$sizeMb"
