# assemble_delivery_package.ps1
# 组装交付包：以既有交付包为基线（保留 data/ 与文档结构），把仓库当前的交付文件同步过去，
# 清理非交付内容，跑自检与一致性校验，并可选打包 .rar。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File assemble_delivery_package.ps1
#   powershell -ExecutionPolicy Bypass -File assemble_delivery_package.ps1 -Version 06 -BaseVersion 05
#   powershell -ExecutionPolicy Bypass -File assemble_delivery_package.ps1 -NoArchive
#
# 注意：本文件必须保存为 UTF-8 with BOM，否则 Windows PowerShell 5.1 会按 ANSI 解析导致中文乱码报错。
param(
    [string]$Version = '05',
    [string]$BaseVersion = '04',
    [switch]$NoArchive
)

$ErrorActionPreference = 'Stop'

$ws     = Split-Path -Parent $MyInvocation.MyCommand.Path      # 仓库根 = antidrone_delivery
$parent = Split-Path $ws -Parent
$base   = Join-Path $parent "antidrone_delivery 提交版_$BaseVersion"
$dest   = Join-Path $parent "antidrone_delivery 提交版_$Version"
$manual = "反无人机行动方案智能生成系统_用户指导手册_v4.3.docx"

# 随仓库同步进交付包的文本/配置类文件（编译产物单独同步）
$syncFiles = @(
    'main_compiled.py',
    'web_app.py',
    'equipment_parser.py',
    'core_imports.py',
    'run_military_research.py',
    'build_military_pyd.py',
    'equipment_library.json',
    'config.example.json',
    'requirements.txt',
    'README.md',
    'sit.txt',
    'assets.txt',
    '环境配置指南.md'
)

if (-not (Test-Path $base)) { throw "基线交付包不存在: $base" }
if (Test-Path $dest)        { throw "目标已存在，请先删除或改用其他版本号: $dest" }

Write-Host "1) 复制基线 提交版_$BaseVersion -> 提交版_$Version"
Copy-Item $base $dest -Recurse -Force

Write-Host "2) 清理非交付内容"
Get-ChildItem $dest -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
Remove-Item (Join-Path $dest 'config.json') -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $dest 'output') -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $dest 'result') -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $dest -Recurse -File -Include '*.cp312-win_amd64.pyd', '*.bak', '*.c' | Remove-Item -Force
Get-ChildItem $dest -Recurse -File -Include '*_v3.0.docx', '*_v4.0.docx', '*_v4.0.pdf', '*_v4.1.docx', '*_v4.2.docx' | Remove-Item -Force

Write-Host "3) 从仓库同步交付文件"
$updated = @()
foreach ($name in $syncFiles) {
    $src = Join-Path $ws $name
    if (-not (Test-Path $src)) { throw "仓库缺少交付文件: $name" }
    $dst = Join-Path $dest $name
    $status = if (-not (Test-Path $dst)) { 'NEW' } elseif ((Get-FileHash $src -Algorithm MD5).Hash -eq (Get-FileHash $dst -Algorithm MD5).Hash) { 'same' } else { 'UPDATED' }
    Copy-Item $src $dst -Force
    if ($status -ne 'same') { $updated += "$name ($status)" }
}
Write-Host ("   变更: " + (($updated | Sort-Object) -join ', '))

Write-Host "4) 同步编译产物（裸名 .pyd，跳过平台标签副本）"
Get-ChildItem (Join-Path $ws '*.pyd') | Where-Object { $_.Name -notlike '*.cp312-win_amd64.pyd' } | ForEach-Object {
    Copy-Item $_.FullName (Join-Path $dest $_.Name) -Force
}
Get-ChildItem (Join-Path $ws 'military_research\*.pyd') | Where-Object { $_.Name -notlike '*.cp312-win_amd64.pyd' } | ForEach-Object {
    Copy-Item $_.FullName (Join-Path (Join-Path $dest 'military_research') $_.Name) -Force
}
Copy-Item (Join-Path $ws 'military_research\__init__.py') (Join-Path $dest 'military_research\__init__.py') -Force

Write-Host "5) 放入最新手册"
Copy-Item (Join-Path $ws $manual) $dest -Force

Write-Host "6) 组装结果"
Get-ChildItem $dest -File | Sort-Object Name | ForEach-Object { "   {0,9}  {1}" -f $_.Length, $_.Name }
Write-Host "   --- military_research/ ---"
Get-ChildItem (Join-Path $dest 'military_research') -File | Sort-Object Name | ForEach-Object { "   {0,9}  {1}" -f $_.Length, $_.Name }
Write-Host "   --- data/ ---"
Get-ChildItem (Join-Path $dest 'data') -File | ForEach-Object { "   {0,9}  {1}" -f $_.Length, $_.Name }

Write-Host "7) 交付包自检"
$bad = @()
if (Test-Path (Join-Path $dest 'config.json')) { $bad += 'config.json（含真实 Key）' }
if (Get-ChildItem $dest -Recurse -File -Filter '*.cp312-win_amd64.pyd') { $bad += '平台标签 .pyd' }
if (Get-ChildItem $dest -Recurse -Directory -Filter '__pycache__') { $bad += '__pycache__' }
if (Get-ChildItem $dest -Recurse -File -Filter '*.bak') { $bad += '*.bak' }
if (Get-ChildItem $dest -Recurse -File -Filter '*.c') { $bad += '*.c（Cython 中间文件）' }
foreach ($devOnly in @('test_equipment_parser.py', 'smoke_test_delivery.py', 'assemble_delivery_package.ps1', 'update_manual_v43.py')) {
    if (Test-Path (Join-Path $dest $devOnly)) { $bad += "开发专用文件 $devOnly" }
}
if (Test-Path (Join-Path $dest 'military_research_backup')) { $bad += 'military_research_backup（源码，不交付）' }
if ($bad.Count -gt 0) { throw ("交付包自检失败: " + ($bad -join ', ')) }
Write-Host "   通过：无 config.json / 无平台标签 .pyd / 无缓存与中间产物 / 无开发专用文件 / 无源码备份"

Write-Host "8) 关键产物一致性校验（与仓库逐字节比对）"
$checks = @(
    @('military_research\engine.pyd', 'military_research\engine.pyd'),
    @('military_research\fast_pipeline.pyd', 'military_research\fast_pipeline.pyd'),
    @('military_research\cli.pyd', 'military_research\cli.pyd'),
    @('main_compiled.py', 'main_compiled.py'),
    @('web_app.py', 'web_app.py'),
    @('equipment_parser.py', 'equipment_parser.py'),
    @('equipment_library.json', 'equipment_library.json')
)
foreach ($pair in $checks) {
    $a = Join-Path $ws $pair[0]
    $b = Join-Path $dest $pair[1]
    if ((Get-FileHash $a -Algorithm MD5).Hash -ne (Get-FileHash $b -Algorithm MD5).Hash) {
        throw "与仓库不一致: $($pair[0])"
    }
}
Write-Host "   engine/fast_pipeline/cli .pyd + main_compiled.py + web_app.py + equipment_parser.py + equipment_library.json 全部一致"

if (-not $NoArchive) {
    Write-Host "9) 打包 .rar"
    $rarExe = 'D:\Program Files\WinRAR\Rar.exe'
    if (Test-Path $rarExe) {
        Push-Location $parent
        try {
            & $rarExe a -r -m3 "antidrone_delivery 提交版_$Version.rar" "antidrone_delivery 提交版_$Version" | Out-Null
        } finally { Pop-Location }
        $rarPath = Join-Path $parent "antidrone_delivery 提交版_$Version.rar"
        Write-Host ("   已生成: {0} ({1} 字节)" -f $rarPath, (Get-Item $rarPath).Length)
    } else {
        Write-Host "   未找到 Rar.exe，跳过打包"
    }
}

Write-Host "完成: $dest"


