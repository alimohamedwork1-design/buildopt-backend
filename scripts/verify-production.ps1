# Verify BuildOpt production health (build-opt.site + Railway backend)
$ErrorActionPreference = "Continue"
$Backend = "https://buildopt-backend-production.up.railway.app/api/v1"
$Frontend = "https://build-opt.site"

Write-Host "=== BuildOpt Production Verification ===" -ForegroundColor Cyan

function Get-Json($url) {
    try {
        return Invoke-RestMethod -Uri $url -TimeoutSec 15 -Method Get
    } catch {
        Write-Host "FAIL $url : $_" -ForegroundColor Red
        return $null
    }
}

$health = Get-Json "$Backend/health"
if ($health) {
    Write-Host "OK  Backend health: $($health.status)" -ForegroundColor Green
    if ($health.PSObject.Properties.Name -contains "demo_mode") {
        Write-Host "    demo_mode=$($health.demo_mode)"
    }
}

$protocols = Get-Json "$Backend/health/protocols"
if ($protocols) {
    $meta = $protocols.metasys
    if ($meta) {
        Write-Host "    Metasys: $($meta.status) ($($meta.response_ms)ms)" -ForegroundColor $(if ($meta.status -match 'connect|health') { 'Green' } else { 'Yellow' })
    }
    $influx = $protocols.influxdb
    if ($influx) {
        Write-Host "    InfluxDB: $($influx.status) points=$($influx.data_points)"
    }
}

$mod = Get-Json "$Backend/modules/overview/data"
if ($mod) {
    Write-Host "OK  Module API demo_mode=$($mod.demo_mode)" -ForegroundColor $(if (-not $mod.demo_mode) { 'Green' } else { 'Yellow' })
}

try {
    $fe = Invoke-WebRequest -Uri $Frontend -TimeoutSec 15 -UseBasicParsing
    Write-Host "OK  Frontend $($fe.StatusCode) $Frontend" -ForegroundColor Green
} catch {
    Write-Host "FAIL Frontend: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Next: set DEMO_MODE=false on Railway when Metasys is connected (see scripts/PRODUCTION_ENV.md)"
