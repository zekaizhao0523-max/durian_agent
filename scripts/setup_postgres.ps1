# 榴莲 Agent — PostgreSQL 18 一键初始化
# 用法:
#   .\scripts\setup_postgres.ps1 -Password "你安装PG时设的密码"
# 或:
#   $env:POSTGRES_PASSWORD="你的密码"; .\scripts\setup_postgres.ps1

param(
    [string]$Password = $env:POSTGRES_PASSWORD,
    [string]$Host = "localhost",
    [int]$Port = 5432,
    [string]$User = "postgres",
    [string]$Database = "durian_agent",
    [string]$PgBin = "D:\PostgreSQL\18\bin"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $Root ".env"

if (-not $Password) {
    Write-Host "请提供 PostgreSQL 密码:" -ForegroundColor Yellow
    $Secure = Read-Host -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    $Password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
}

if (-not (Test-Path $PgBin)) {
    throw "未找到 PostgreSQL bin 目录: $PgBin，请修改 -PgBin 参数"
}

$env:PGPASSWORD = $Password
$psql = Join-Path $PgBin "psql.exe"
$pgIsready = Join-Path $PgBin "pg_isready.exe"

Write-Host "检查 PostgreSQL 连接..." -ForegroundColor Cyan
& $pgIsready -h $Host -p $Port | Out-Null
$test = & $psql -h $Host -p $Port -U $User -d postgres -tAc "SELECT 1" 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "连接失败，请检查密码与服务。错误: $test"
}
Write-Host "连接成功" -ForegroundColor Green

# 更新 .env
$encoded = [uri]::EscapeDataString($Password)
$dbUrl = "postgresql://${User}:${encoded}@${Host}:${Port}/${Database}"
$content = Get-Content $EnvFile -Raw -Encoding UTF8
if ($content -match "DATABASE_URL=.*") {
    $content = $content -replace "DATABASE_URL=.*", "DATABASE_URL=$dbUrl"
} else {
    $content += "`nDATABASE_URL=$dbUrl`n"
}
# 去掉 SQLite 行（若存在）
$content = $content -replace "DATABASE_URL=sqlite:///.*\r?\n?", ""
Set-Content $EnvFile $content.TrimEnd() -Encoding UTF8 -NoNewline
Add-Content $EnvFile "`n" -Encoding UTF8
Write-Host "已更新 .env" -ForegroundColor Green

# 初始化表结构
Push-Location $Root
python scripts/init_postgres.py --create-db
if ($LASTEXITCODE -ne 0) { throw "init_postgres.py 失败" }
python test_memory.py
Pop-Location

Write-Host ""
Write-Host "完成! 启动服务:" -ForegroundColor Green
Write-Host "  uvicorn src.main:app --reload --host 127.0.0.1 --port 8080"
Write-Host "验证: http://localhost:8080/api/v1/health  (database 应为 postgresql)"
