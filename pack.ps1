# =============================================================================
# 离线打包（唯一实现）。入口：pack.ps1 或 pack.bat（参数相同）
# 输出：dist_package\  → zip 后拷到内网，在 Linux 上执行 deploy_offline.sh（不要在本机跑 pack.bat 当部署）
#
# 已自动包含（无需再手动 npm run build / 手抄 dist）：
#   [2/5] 在 frontend\ 下执行 npm install + npm run build，
#         并把 frontend\dist\ 内全部文件同步到 dist_package\frontend_dist\（先清空旧目录，避免旧 JS 残留）。
#
# 防「打到旧代码」：
#   - 根目录固定为 **本脚本所在目录**（$PSScriptRoot），勿把 pack.ps1 单独拷到别处执行。
#   - 构建前删除 frontend\dist，强制 Vite 全量产出，避免残留旧 chunk。
#   - 复制 backend 后删除 dist_package 内 __pycache__。
#   - 生成 dist_package\PACK_MANIFEST.txt（时间、ROOT、git 提交），zip 前请核对。
#
# -SkipDockerPull : 不 pull；本机 Docker 需已有 python:3.11-slim / nginx:alpine 才能 save
# -SkipDockerSave : 不 pull/save；需事先放入 dist_package\images\*.tar（见脚本内说明）
# =============================================================================
param(
    [switch]$SkipDockerPull,
    [switch]$SkipDockerSave
)

$ROOT = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$OUT = Join-Path $ROOT "dist_package"

if ($env:PACK_PYTHON_IMAGE) { $PythonImage = $env:PACK_PYTHON_IMAGE } else { $PythonImage = "python:3.11-slim" }
if ($env:PACK_NGINX_IMAGE)  { $NginxImage  = $env:PACK_NGINX_IMAGE }  else { $NginxImage  = "nginx:alpine" }

function Test-DockerImageLocal {
    param([string]$Ref)
    docker image inspect $Ref 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Save-DockerImage {
    param(
        [string]$Ref,
        [string]$TarPath,
        [switch]$SkipPull
    )
    if (-not $SkipPull) {
        Write-Host ("  docker pull " + $Ref)
        docker pull $Ref
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  (pull failed, try local image)" -ForegroundColor Yellow
        }
    }
    else {
        Write-Host ("  skip pull, local: " + $Ref)
    }
    if (-not (Test-DockerImageLocal -Ref $Ref)) {
        Write-Host ""
        Write-Host "This PC Docker does not have image: $Ref" -ForegroundColor Red
        Write-Host "Fix one of:" -ForegroundColor Yellow
        Write-Host "  1) docker pull $Ref   (Docker Desktop running, network OK)"
        Write-Host "  2) docker load -i xxx.tar   then: docker tag ... $Ref"
        Write-Host "  3) Re-run: .\pack.ps1 -SkipDockerSave   after copying tars from server to:"
        Write-Host "     $OUT\images\python3.11-slim.tar"
        Write-Host "     $OUT\images\nginx-alpine.tar"
        Write-Host ""
        Write-Error ("Missing Docker image: " + $Ref)
        exit 1
    }
    Write-Host ("  docker save -> " + $TarPath)
    docker save $Ref -o $TarPath
    if ($LASTEXITCODE -ne 0) {
        Write-Error ("docker save failed: " + $Ref)
        exit 1
    }
}

New-Item -ItemType Directory -Force -Path "$OUT\wheels" | Out-Null
New-Item -ItemType Directory -Force -Path "$OUT\images" | Out-Null

Write-Host ""
Write-Host "======== 打包根目录（请确认是你要发布的仓库）========" -ForegroundColor Cyan
Write-Host "  $ROOT"
Write-Host "====================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/5] Downloading Python wheels..."
pip download --no-cache-dir -r "$ROOT\backend\requirements.txt" `
    -d "$OUT\wheels" `
    --platform manylinux2014_x86_64 `
    --python-version 311 `
    --only-binary=:all:
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host '[2/5] 前端：npm install + npm run build → 同步到 dist_package\frontend_dist\'
$feDist = Join-Path $ROOT "frontend\dist"
if (Test-Path $feDist) {
    Write-Host "  清理旧 frontend\dist（强制全量构建）..."
    Remove-Item -Recurse -Force $feDist
}
Set-Location "$ROOT\frontend"
npm install
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
npm run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Set-Location $ROOT
if (Test-Path "$OUT\frontend_dist") {
    Remove-Item -Recurse -Force "$OUT\frontend_dist"
}
New-Item -ItemType Directory -Force -Path "$OUT\frontend_dist" | Out-Null
Copy-Item -Recurse -Force "$ROOT\frontend\dist\*" (Join-Path $OUT 'frontend_dist')
Write-Host "  → frontend_dist 已更新（与 frontend\dist 一致）"

Write-Host ("[3/5] Docker images: " + $PythonImage + ", " + $NginxImage)
$pyTar = Join-Path $OUT "images\python3.11-slim.tar"
$ngxTar = Join-Path $OUT "images\nginx-alpine.tar"
if ($SkipDockerSave) {
    Write-Host '  -SkipDockerSave: using existing tars under images\'
    if (-not (Test-Path $pyTar)) {
        Write-Error ("File not found: " + $pyTar)
        exit 1
    }
    if (-not (Test-Path $ngxTar)) {
        Write-Error ("File not found: " + $ngxTar)
        exit 1
    }
    if ((Get-Item $pyTar).Length -lt 4096) {
        Write-Error ("Too small (corrupt?): " + $pyTar)
        exit 1
    }
    if ((Get-Item $ngxTar).Length -lt 4096) {
        Write-Error ("Too small (corrupt?): " + $ngxTar)
        exit 1
    }
    Write-Host "  OK:" $pyTar "," $ngxTar
}
else {
    Save-DockerImage -Ref $PythonImage -TarPath $pyTar -SkipPull:$SkipDockerPull
    Save-DockerImage -Ref $NginxImage  -TarPath $ngxTar -SkipPull:$SkipDockerPull
}

Write-Host "[4/5] Copying source files..."
if (Test-Path "$OUT\backend") { Remove-Item -Recurse -Force "$OUT\backend" }
if (Test-Path "$OUT\frontend") { Remove-Item -Recurse -Force "$OUT\frontend" }
Copy-Item -Recurse -Force "$ROOT\backend" "$OUT\backend"
Copy-Item -Recurse -Force "$ROOT\frontend" "$OUT\frontend"
Get-ChildItem -Path "$OUT\backend" -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -Force "$ROOT\docker-compose.yml" $OUT
Copy-Item -Force "$ROOT\deploy_offline.sh" $OUT
if (Test-Path "$ROOT\scripts") {
    if (Test-Path "$OUT\scripts") { Remove-Item -Recurse -Force "$OUT\scripts" }
    Copy-Item -Recurse -Force "$ROOT\scripts" "$OUT\scripts"
    Write-Host '  -> scripts 已复制（含 check_ssh_ports.py 等）'
}

$gitHead = ""
Push-Location $ROOT
try {
    $gitHead = (& git rev-parse HEAD 2>$null)
    if (-not $gitHead) { $gitHead = "(not a git repo or git missing)" }
} finally {
    Pop-Location
}
$manifestLines = @(
    'PACK_MANIFEST (offline bundle)',
    ('Generated (local): ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')),
    ('ROOT (packed from): ' + $ROOT),
    ('Git HEAD: ' + $gitHead),
    '',
    'Check: backend/main.py, deploy_offline.sh, and this manifest should be in the package root.'
)
$manifest = [string]::Join([Environment]::NewLine, $manifestLines)
Set-Content -Path (Join-Path $OUT 'PACK_MANIFEST.txt') -Value $manifest -Encoding UTF8

Write-Host '[5/5] Validating packaged files...'
$mustExist = @(
    "$OUT\backend\main.py",
    "$OUT\backend\restart.py",
    "$OUT\frontend\src\components\ModelFormAdd.vue",
    "$OUT\deploy_offline.sh",
    "$OUT\PACK_MANIFEST.txt"
)
foreach ($p in $mustExist) {
    if (-not (Test-Path $p)) {
        Write-Error ('Missing packaged file: ' + $p)
        exit 1
    }
}
$mainPy = Get-Content "$OUT\backend\main.py" -Raw
$restartPy = Get-Content "$OUT\backend\restart.py" -Raw
$addVue = Get-Content "$OUT\frontend\src\components\ModelFormAdd.vue" -Raw
if ($mainPy -notmatch '"ssh_port": body\.ssh_port') {
    Write-Error "Packaged backend/main.py is stale: missing direct ssh_port storage."
    exit 1
}
if ($mainPy -notmatch 'ssh_port_val = int\(dec\.get\("ssh_port"\) or 22\)') {
    Write-Error "Packaged backend/main.py is stale: missing restart ssh_port readback."
    exit 1
}
if ($restartPy -notmatch 'ssh_port = _safe_ssh_port\(ssh_port\)') {
    Write-Error "Packaged backend/restart.py is stale: missing safe ssh_port normalization."
    exit 1
}
if ($addVue -notmatch 'SSH 端口') {
    Write-Error "Packaged frontend ModelFormAdd.vue is stale: missing SSH port field."
    exit 1
}

Write-Host ("Done! Package: " + $OUT)
Write-Host "  PACK_MANIFEST.txt written. Check it before zipping." -ForegroundColor Green
Write-Host "  Package validation passed." -ForegroundColor Green
