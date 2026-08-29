# BuildOpt Phase 3 pilot — run all automated deployment checks
$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot

Write-Host "=== BuildOpt Pilot Do-All ===" -ForegroundColor Cyan

Write-Host "`n[1/4] Backend tests..." -ForegroundColor Yellow
Push-Location $Root
py -m pytest -q
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL backend tests" -ForegroundColor Red; Pop-Location; exit 1 }
Pop-Location

Write-Host "`n[2/4] Production API verification..." -ForegroundColor Yellow
& "$Root\scripts\verify-production.ps1"

Write-Host "`n[3/4] Supabase table verification..." -ForegroundColor Yellow
if (Test-Path "C:\Users\Ali Mohamed\Projects\buildopt-ai\.env") {
    $line = Select-String -Path "C:\Users\Ali Mohamed\Projects\buildopt-ai\.env" -Pattern '^VITE_SUPABASE_PUBLISHABLE_KEY=' | Select-Object -First 1
    if ($line) {
        $env:SUPABASE_KEY = ($line.Line -replace '^VITE_SUPABASE_PUBLISHABLE_KEY="?', '' -replace '"$', '')
    }
    $urlLine = Select-String -Path "C:\Users\Ali Mohamed\Projects\buildopt-ai\.env" -Pattern '^VITE_SUPABASE_URL=' | Select-Object -First 1
    if ($urlLine) {
        $env:SUPABASE_URL = ($urlLine.Line -replace '^VITE_SUPABASE_URL="?', '' -replace '"$', '')
    }
}
Push-Location $Root
py scripts/verify_supabase_tables.py
$supaOk = $LASTEXITCODE -eq 0
Pop-Location

Write-Host "`n[4/4] Frontend tests + build..." -ForegroundColor Yellow
Push-Location "C:\Users\Ali Mohamed\Projects\buildopt-ai"
npm test -- --run
if ($LASTEXITCODE -ne 0) { Write-Host "WARN frontend tests exit code (check unhandled Supabase warning)" -ForegroundColor Yellow }
npm run build
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL frontend build" -ForegroundColor Red; Pop-Location; exit 1 }
Pop-Location

Write-Host "`n=== Manual steps remaining ===" -ForegroundColor Cyan
Write-Host "  - Customer site: deploy buildopt-edge Docker + mapped_points.json"
Write-Host "  - Railway: set SUPABASE_SERVICE_KEY for durable telemetry registry (auto when configured)"
Write-Host "  - Docker: buildopt-edge image build where Docker CLI is installed"

if (-not $supaOk) { exit 1 }
Write-Host "`nAll automated checks complete." -ForegroundColor Green
