$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$OUT = Join-Path $ROOT "dist_package"

New-Item -ItemType Directory -Force -Path "$OUT\wheels" | Out-Null
New-Item -ItemType Directory -Force -Path "$OUT\images" | Out-Null

Write-Host "[1/5] Downloading Python wheels..."
pip download -r "$ROOT\backend\requirements.txt" `
    -d "$OUT\wheels" `
    --platform manylinux2014_x86_64 `
    --python-version 311 `
    --only-binary=:all:

Write-Host "[2/5] Building frontend..."
Set-Location "$ROOT\frontend"
npm install
npm run build
New-Item -ItemType Directory -Force -Path "$OUT\frontend_dist" | Out-Null
Copy-Item -Recurse -Force "$ROOT\frontend\dist\*" "$OUT\frontend_dist\"

Write-Host "[3/5] Pulling and saving Docker images..."
docker pull python:3.11-slim
docker save python:3.11-slim -o "$OUT\images\python3.11-slim.tar"
docker pull nginx:alpine
docker save nginx:alpine -o "$OUT\images\nginx-alpine.tar"

Write-Host "[4/5] Copying source files..."
Copy-Item -Recurse -Force "$ROOT\backend" "$OUT\backend"
Copy-Item -Recurse -Force "$ROOT\frontend" "$OUT\frontend"
Copy-Item -Force "$ROOT\docker-compose.yml" "$OUT\"
Copy-Item -Force "$ROOT\deploy_offline.sh" "$OUT\"

Write-Host "[5/5] Done! Package saved to: $OUT"
Read-Host "Press Enter to exit"
