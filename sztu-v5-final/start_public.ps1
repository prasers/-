Param(
    [string]$PublicBaseUrl = "",
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

if ($PublicBaseUrl -eq "") {
    $PublicBaseUrl = $env:PUBLIC_BASE_URL
}

if ($PublicBaseUrl -eq "") {
    Write-Host "[INFO] 未设置 PUBLIC_BASE_URL，二维码将显示局域网地址。" -ForegroundColor Yellow
} else {
    $env:PUBLIC_BASE_URL = $PublicBaseUrl
    Write-Host "[INFO] PUBLIC_BASE_URL = $($env:PUBLIC_BASE_URL)" -ForegroundColor Cyan
}

Write-Host "[INFO] 项目目录: $projectRoot" -ForegroundColor Gray
Write-Host "[INFO] 启动 Streamlit 服务 (0.0.0.0:$Port)..." -ForegroundColor Green

python -m streamlit run app.py --server.address 0.0.0.0 --server.port $Port
