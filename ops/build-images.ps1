param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v[0-9]+$')]
    [string]$Version,

    [string]$TagDate = (Get-Date -Format 'yyyyMMdd'),

    [string]$Registry = 'hkccr.ccs.tencentyun.com',

    [string]$Namespace = 'moyu',

    [ValidateSet('all', 'api', 'seesea', 'frontend', 'nginx')]
    [string[]]$Service = @('all'),

    [switch]$Push,

    [switch]$NoLatest
)

$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$tag = "$TagDate-$Version"
$prefix = "$Registry/$Namespace"
$buildAll = $Service -contains 'all'

function Build-Image {
    param(
        [string]$Name,
        [string[]]$BuildArgs
    )

    $image = "$prefix/moyu-$Name`:$tag"
    $latest = "$prefix/moyu-$Name`:latest"
    $tags = @('-t', $image)
    if (-not $NoLatest) {
        $tags += @('-t', $latest)
    }

    Write-Host ""
    Write-Host "==> Building $image" -ForegroundColor Cyan
    docker build @tags @BuildArgs
    if ($LASTEXITCODE -ne 0) {
        throw "docker build failed for $image"
    }

    if ($Push) {
        Write-Host "==> Pushing $image" -ForegroundColor Cyan
        docker push $image
        if ($LASTEXITCODE -ne 0) {
            throw "docker push failed for $image"
        }
        if (-not $NoLatest) {
            Write-Host "==> Pushing $latest" -ForegroundColor Cyan
            docker push $latest
            if ($LASTEXITCODE -ne 0) {
                throw "docker push failed for $latest"
            }
        }
    }
}

Push-Location $repoRoot
try {
    if ($buildAll -or $Service -contains 'api') {
        Build-Image 'api' @('-f', 'backend/Dockerfile', '.')
    }

    if ($buildAll -or $Service -contains 'seesea') {
        Build-Image 'seesea' @('-f', 'ops/seesea.Dockerfile', '.')
    }

    if ($buildAll -or $Service -contains 'frontend') {
        Build-Image 'frontend' @(
            '--build-arg', 'API_BASE=http://api:8000/api',
            '-f', 'frontend/Dockerfile',
            'frontend'
        )
    }

    if ($buildAll -or $Service -contains 'nginx') {
        Build-Image 'nginx' @('-f', 'ops/nginx.Dockerfile', '.')
    }

    Write-Host ""
    Write-Host "Done. Tag: $tag" -ForegroundColor Green
} finally {
    Pop-Location
}
