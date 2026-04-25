Param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

Write-Host "[STEP 1/2] 启动 Streamlit (后台)..." -ForegroundColor Green
$streamlitProc = Start-Process powershell -PassThru -WindowStyle Normal -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location `"$projectRoot`"; python -m streamlit run app.py --server.address 0.0.0.0 --server.port $Port"
)

Start-Sleep -Seconds 2

Write-Host "[STEP 2/2] 启动 cloudflared tunnel..." -ForegroundColor Green
Write-Host "[INFO] 若提示命令不存在，请先安装 cloudflared 并加入 PATH" -ForegroundColor Yellow
Write-Host "[INFO] 外网地址会在 cloudflared 窗口输出（https://xxxxx.trycloudflare.com）" -ForegroundColor Cyan

cloudflared tunnel --url "http://localhost:$Port"
