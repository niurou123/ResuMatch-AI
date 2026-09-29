@echo off
REM 安装后端依赖（走清华 PyPI 镜像）
cd /d "%~dp0.."
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple