# One-time local PostgreSQL bootstrap (temporary trust auth)
param(
    [string]$DataDir = "D:\PostgreSQL\18\data",
    [string]$PgBin = "D:\PostgreSQL\18\bin",
    [string]$NewPassword = "durian_agent_local",
    [string]$Database = "durian_agent"
)

$ErrorActionPreference = "Stop"
$Hba = Join-Path $DataDir "pg_hba.conf"
$Backup = "$Hba.bak.agent"
$Root = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $Root ".env"

if (-not (Test-Path $Hba)) { throw "pg_hba.conf not found: $Hba" }

Copy-Item $Hba $Backup -Force
$content = Get-Content $Hba -Raw
$content = $content -replace "(host\s+all\s+all\s+127\.0\.0\.1/32\s+)scram-sha-256", '${1}trust'
$content = $content -replace "(host\s+all\s+all\s+::1/128\s+)scram-sha-256", '${1}trust'
Set-Content $Hba $content -NoNewline

& (Join-Path $PgBin "pg_ctl.exe") reload -D $DataDir
Start-Sleep -Seconds 2

$psql = Join-Path $PgBin "psql.exe"
& $psql -h localhost -U postgres -d postgres -c "SELECT 1" | Out-Null

$exists = (& $psql -h localhost -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$Database'").Trim()
if ($exists -ne "1") {
    & $psql -h localhost -U postgres -d postgres -c "CREATE DATABASE $Database"
    Write-Host "Created database: $Database"
} else {
    Write-Host "Database exists: $Database"
}

& $psql -h localhost -U postgres -d postgres -c "ALTER USER postgres PASSWORD '$NewPassword';"
Write-Host "Set postgres password"

Copy-Item $Backup $Hba -Force
& (Join-Path $PgBin "pg_ctl.exe") reload -D $DataDir

$encoded = [uri]::EscapeDataString($NewPassword)
$dbUrl = "postgresql://postgres:${encoded}@localhost:5432/${Database}"
$envText = Get-Content $EnvFile -Raw -Encoding UTF8
$envText = $envText -replace "DATABASE_URL=.*(\r?\n)?", ""
$envText = $envText.TrimEnd() + "`r`nDATABASE_URL=$dbUrl`r`n"
Set-Content $EnvFile $envText -Encoding UTF8
Write-Host "Updated .env"

Push-Location $Root
$env:DATABASE_URL = $dbUrl
python scripts/init_postgres.py
if ($LASTEXITCODE -ne 0) { throw "init_postgres failed" }
python test_memory.py
if ($LASTEXITCODE -ne 0) { throw "test_memory failed" }
Pop-Location

Write-Host "DONE. Password: $NewPassword"
