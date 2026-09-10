# assemble_delivery_package.ps1
# 组装交付包：以既有交付包为基线，替换本版本变更的文件，并清理非交付内容。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File assemble_delivery_package.ps1
#   powershell -ExecutionPolicy Bypass -File assemble_delivery_package.ps1 -Version 06 -BaseVersion 05
#
# 注意：本文件必须保存为 UTF-8 with BOM，否则 Windows PowerShell 5.1 会按 ANSI 解析导致中文乱码报错。
param(
    [string]$Version = '05',
    [string]$BaseVersion = '04'
)

$ErrorActionPreference = 'Stop'

$ws     = Split-Path -Parent $MyInvocation.MyCommand.Path      # 仓库根 = antidrone_delivery
$parent = Split-Path $ws -Parent
$base   = Join-Path $parent "antidrone_delivery 提交版_$BaseVersion"
$dest   = Join-Path $parent "antidrone_delivery 提交版_$Version"
$manual = "反无人机行动方案智能生成系统_用户指导手册_v4.3.docx"

if (-not (Test-Path $base)) { throw "基线交付包不存在: $base" }
if (Test-Path $dest)        { throw "目标已存在，请先确认是否要覆盖: $dest" }

Write-Host "1) 复制基线 提交版_$BaseVersion -> 提交版_$Version"
Copy-Item $base $dest -Recurse -Force

Write-Host "2) 清理非交付内容（缓存 / 真实配置 / 测试产物 / 重复或历史产物）"
Get-ChildItem $dest -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Remove-Item (Join-Path $dest 'config.json') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $dest 'output') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $dest 'result') -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $dest -Recurse -File -Include '*.cp312-win_amd64.pyd', '*.bak' | Remove-Item -Force
Get-ChildItem $dest -Recurse -File -Include '*_v3.0.docx', '*_v4.0.docx', '*_v4.0.pdf', '*_v4.1.docx', '*_v4.2.docx' | Remove-Item -Force

Write-Host "3) 替换本版本变更的编译产物"
Copy-Item (Join-Path $ws 'military_research\engine.pyd') (Join-Path $dest 'military_research\engine.pyd') -Force

Write-Host "4) 放入最新手册"
Copy-Item (Join-Path $ws $manual) $dest -Force

Write-Host "5) 组装结果"
Get-ChildItem $dest -File | Sort-Object Name | ForEach-Object { "   {0,9}  {1}" -f $_.Length, $_.Name }
Write-Host "   --- military_research/ ---"
Get-ChildItem (Join-Path $dest 'military_research') -File | Sort-Object Name | ForEach-Object { "   {0,9}  {1}" -f $_.Length, $_.Name }
Write-Host "   --- data/ ---"
Get-ChildItem (Join-Path $dest 'data') -File | ForEach-Object { "   {0,9}  {1}" -f $_.Length, $_.Name }

Write-Host "6) 交付包自检"
$bad = @()
if (Test-Path (Join-Path $dest 'config.json')) { $bad += 'config.json（含真实 Key）' }
if (Get-ChildItem $dest -Recurse -File -Filter '*.cp312-win_amd64.pyd') { $bad += '平台标签 .pyd' }
if (Get-ChildItem $dest -Recurse -Directory -Filter '__pycache__') { $bad += '__pycache__' }
if (Get-ChildItem $dest -Recurse -File -Filter '*.bak') { $bad += '*.bak' }
if (Get-ChildItem $dest -Recurse -File -Filter '*.c') { $bad += '*.c（Cython 中间文件）' }
if ($bad.Count -gt 0) { throw ("交付包自检失败: " + ($bad -join ', ')) }
Write-Host "   通过：无 config.json / 无平台标签 .pyd / 无 __pycache__ / 无 .bak / 无 .c"

Write-Host "7) 打包 .rar（若存在 WinRAR）"
$rarExe = 'D:\Program Files\WinRAR\Rar.exe'
if (Test-Path $rarExe) {
    Push-Location $parent
    try {
        & $rarExe a -r -m3 "antidrone_delivery 提交版_$Version.rar" "antidrone_delivery 提交版_$Version" | Out-Null
    } finally { Pop-Location }
    $rarPath = Join-Path $parent "antidrone_delivery 提交版_$Version.rar"
    Write-Host ("   已生成: {0} ({1} 字节)" -f $rarPath, (Get-Item $rarPath).Length)
} else {
    Write-Host "   未找到 Rar.exe，跳过打包（可手动压缩）"
}

Write-Host "完成: $dest"

