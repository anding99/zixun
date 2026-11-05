# -*- coding: utf-8 -*-
"""生成启动器与快捷方式（一次性脚本，可保留）"""
from pathlib import Path

ROOT = Path(r"F:\DEEPSEEK\资讯")

PS1 = r'''# 资讯 · 本地服务启动器
# 作用：如果 8790 端口没有服务，就在后台起一个；然后用默认浏览器打开。
$ErrorActionPreference = 'SilentlyContinue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$port = 8790

function Test-Port([int]$p) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $p)
        $c.Close()
        return $true
    } catch { return $false }
}

if (-not (Test-Port $port)) {
    $candidates = @(
        (Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'),
        'C:\Python312\python.exe'
    )
    $py = $null
    foreach ($c in $candidates) { if (Test-Path $c) { $py = $c; break } }
    if (-not $py) {
        $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($cmd) { $py = $cmd.Source }
    }
    if (-not $py) {
        Write-Host "找不到 Python，无法启动本地服务。" -ForegroundColor Red
        Write-Host "可以直接双击：$root\站点\index.html"
        Start-Sleep -Seconds 6
        exit 1
    }
    Start-Process -FilePath $py `
        -ArgumentList @((Join-Path $root 'serve.py'), '--port', "$port") `
        -WorkingDirectory $root -WindowStyle Hidden
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 250
        if (Test-Port $port) { break }
    }
}

Start-Process "http://127.0.0.1:$port/"
'''

CMD = r'''@echo off
rem 打开《资讯》个人情报台（必要时自动启动本地服务）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0启动资讯台.ps1"
'''

URL = """[InternetShortcut]
URL=http://127.0.0.1:8790/
IconIndex=0
"""

(ROOT / "启动资讯台.ps1").write_text(PS1, encoding="utf-8-sig")
(ROOT / "打开资讯台.cmd").write_text(CMD, encoding="gbk")
(ROOT / "资讯台.url").write_text(URL, encoding="gbk")
print("launchers written")
