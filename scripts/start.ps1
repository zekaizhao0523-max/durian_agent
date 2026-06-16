# 榴莲 Agent 启动脚本（默认 8080）
param(
    [int]$Port = 8080,
    [switch]$Reload,
    [switch]$NoKill
)

[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = "1"

$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root

$args = @("run.py", "--port", $Port)
if ($Reload) { $args += "--reload" }
if ($NoKill) { $args += "--no-kill" }

python @args
Pop-Location
