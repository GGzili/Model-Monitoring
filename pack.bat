@echo off
setlocal
set ROOT=%~dp0
set OUT=%ROOT%dist_package

echo === 创建输出目录 ===
mkdir "%OUT%" 2>nul
mkdir "%OUT%\wheels" 2>nul
mkdir "%OUT%\images" 2>nul

echo === 下载 Python wheels ===
pip download -r "%ROOT%backend\requirements.txt" -d "%OUT%\wheels" --platform manylinux2014_x86_64 --python-version 311 --only-binary=:all:

echo === 构建前端 ===
cd /d "%ROOT%frontend"
call npm install
call npm run build
mkdir "%OUT%\frontend_dist" 2>nul
xcopy /E /I /Y "%ROOT%frontend\dist" "%OUT%\frontend_dist"

echo === 拉取并保存 Docker 镜像 ===
docker pull python:3.11-slim
docker save python:3.11-slim -o "%OUT%\images\python3.11-slim.tar"
docker pull nginx:alpine
docker save nginx:alpine -o "%OUT%\images\nginx-alpine.tar"

echo === 复制项目源码 ===
mkdir "%OUT%\backend" 2>nul
xcopy /E /I /Y "%ROOT%backend" "%OUT%\backend"
mkdir "%OUT%\frontend" 2>nul
xcopy /E /I /Y "%ROOT%frontend" "%OUT%\frontend"
copy "%ROOT%docker-compose.yml" "%OUT%\"

echo === 打包完成，输出目录：%OUT% ===
pause
