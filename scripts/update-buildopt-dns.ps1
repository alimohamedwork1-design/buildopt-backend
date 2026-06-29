# Updates build-opt.site DNS at Namecheap to point to Railway.
# Requires Namecheap API access (Profile -> Tools -> API Access).
# Whitelist your public IP (currently shown when you run this script).

param(
    [string]$ApiUser = $env:NAMECHEAP_API_USER,
    [string]$ApiKey = $env:NAMECHEAP_API_KEY,
    [string]$UserName = $env:NAMECHEAP_USERNAME,
    [string]$ClientIp = $env:NAMECHEAP_CLIENT_IP
)

$ErrorActionPreference = "Stop"

$Domain = "build-opt.site"
$RailwayCname = "ftjko43y.up.railway.app"
$RailwayVerify = "railway-verify=34e52b9f2cbd7d836d66e5c6f6b425013a7a0aa42b2b04525fc3dda07b16fcea"

if (-not $ClientIp) {
    $ClientIp = (Invoke-RestMethod -Uri "https://api.ipify.org?format=json").ip
}

if (-not $ApiUser -or -not $ApiKey -or -not $UserName) {
    Write-Host "Missing Namecheap API credentials."
    Write-Host "Set env vars: NAMECHEAP_API_USER, NAMECHEAP_API_KEY, NAMECHEAP_USERNAME"
    Write-Host "Optional: NAMECHEAP_CLIENT_IP (defaults to $ClientIp)"
    Write-Host ""
    Write-Host "Manual DNS at Namecheap Advanced DNS for $Domain`:"
    Write-Host "  1. Remove A record @ -> 185.158.133.1 (Lovable)"
    Write-Host "  2. Add CNAME @ -> $RailwayCname"
    Write-Host "  3. Add TXT _railway-verify -> $RailwayVerify"
    exit 1
}

$base = "https://api.namecheap.com/xml.response"
$query = @{
    ApiUser   = $ApiUser
    ApiKey    = $ApiKey
    UserName  = $UserName
    ClientIp  = $ClientIp
    Command   = "namecheap.domains.dns.setHosts"
    SLD       = "build-opt"
    TLD       = "site"
    HostName1 = "@"
    RecordType1 = "CNAME"
    Address1  = $RailwayCname
    TTL1      = "300"
    HostName2 = "_railway-verify"
    RecordType2 = "TXT"
    Address2  = $RailwayVerify
    TTL2      = "300"
}

$uri = $base + "?" + (($query.GetEnumerator() | ForEach-Object { "{0}={1}" -f [uri]::EscapeDataString($_.Key), [uri]::EscapeDataString([string]$_.Value) }) -join "&")
$response = Invoke-WebRequest -Uri $uri -UseBasicParsing
Write-Host $response.Content

if ($response.Content -match 'Status="OK"') {
    Write-Host "DNS updated. Verify with: railway domain status build-opt.site"
} else {
    Write-Host "Namecheap API did not return OK. Check credentials and IP whitelist ($ClientIp)."
    exit 1
}
