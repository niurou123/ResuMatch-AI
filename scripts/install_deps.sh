#!/usr/bin/env bash
# 安装后端依赖（走清华 PyPI 镜像，避免默认源网络中断）
set -e
cd "$(dirname "$0")/.."
.venv/Scripts/python.exe -m pip install -r requirements.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple