# Verify BuildOpt production health (build-opt.site + Railway backend)
$ErrorActionPreference = "Continue"
$Backend = "https://buildopt-backend-production.up.railway.app/api/v1"
$Frontend = "https://build-opt.site"
$ExpectDemoMode = $env:EXPECT_DEMO_MODE

Write-Host "=== BuildOpt Production Verification ===" -ForegroundColor Cyan

function Get-Json($url, $method = "Get", $headers = @{}) {
    try {
        return Invoke-RestMethod -Uri $url -TimeoutSec 15 -Method $method -Headers $headers
    } catch {
        Write-Host "FAIL $url : $_" -ForegroundColor Red
        return $null
    }
}

$health = Get-Json "$Backend/health"
if ($health) {
    Write-Host "OK  Backend health: $($health.status) score=$($health.health_score)" -ForegroundColor Green
    if ($health.PSObject.Properties.Name -contains "demo_mode") {
        $dm = $health.demo_mode
        Write-Host "    demo_mode=$dm"
        if ($ExpectDemoMode -ne $null -and "$dm" -ne "$ExpectDemoMode") {
            Write-Host "WARN demo_mode=$dm expected $ExpectDemoMode" -ForegroundColor Yellow
        }
    }
}

$connections = Get-Json "$Backend/health/connections"
if ($connections) {
    Write-Host "    influx=$($connections.influxdb) supabase=$($connections.supabase) jci=$($connections.jci_metasys)"
    Write-Host "    ingest_api=$($connections.ingest_api) alert_webhook=$($connections.alert_webhook)"
}

$protocols = Get-Json "$Backend/health/protocols"
if ($protocols) {
    foreach ($p in $protocols.protocols) {
        $color = if ($p.status -match 'connect|health') { 'Green' } else { 'Yellow' }
        Write-Host "    $($p.key): $($p.status) pts=$($p.data_points) ms=$($p.response_ms)" -ForegroundColor $color
    }
}

$mod = Get-Json "$Backend/modules/overview/data"
if ($mod) {
    Write-Host "OK  Module API demo_mode=$($mod.demo_mode)" -ForegroundColor $(if (-not $mod.demo_mode) { 'Green' } else { 'Yellow' })
}

$ingestStatus = Get-Json "$Backend/ingest/status"
if ($ingestStatus) {
    Write-Host "    ingest_enabled=$($ingestStatus.ingest_enabled) key_required=$($ingestStatus.ingest_key_required)"
}

# Ingest key rejection (expect 401 without key in production)
try {
    Invoke-RestMethod -Uri "$Backend/ingest/live" -Method Post -Body '{}' -ContentType 'application/json' -TimeoutSec 10 -ErrorAction Stop
    Write-Host "WARN ingest/live accepted without API key" -ForegroundColor Yellow
} catch {
    if ($_.Exception.Response.StatusCode.value__ -in 401, 422, 503) {
        Write-Host "OK  ingest/live rejects unauthenticated requests" -ForegroundColor Green
    }
}

$alertTest = Get-Json "$Backend/health/alert-webhook/test" "Post"
if ($alertTest) {
    Write-Host "    alert-webhook/test: $($alertTest.status)" -ForegroundColor $(if ($alertTest.status -eq 'ok') { 'Green' } else { 'Yellow' })
}

try {
    $fe = Invoke-WebRequest -Uri $Frontend -TimeoutSec 15 -UseBasicParsing
    Write-Host "OK  Frontend $($fe.StatusCode) $Frontend" -ForegroundColor Green
} catch {
    Write-Host "FAIL Frontend: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Supabase: run python scripts/verify_supabase_tables.py"
Write-Host "Cutover: set DEMO_MODE=false when Metasys + Influx are ready (see scripts/PRODUCTION_ENV.md)"
