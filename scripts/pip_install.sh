#!/usr/bin/env bash
# 安装后端依赖：清华镜像 + 断网自动重试 + 全程日志
# 用法: bash scripts/pip_install.sh
cd "$(dirname "$0")/.." || exit 1

LOG=pip_install.log
PY=.venv/Scripts/python.exe
MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple

: > "$LOG"
echo "===== 开始安装 @ $(date '+%Y-%m-%d %H:%M:%S') =====" >> "$LOG"

for i in 1 2 3 4 5; do
  echo "===== 第 $i 次尝试 @ $(date '+%H:%M:%S') =====" >> "$LOG"
  if "$PY" -m pip install -r requirements.txt \
       -i "$MIRROR" \
       --progress-bar off \
       --no-input >> "$LOG" 2>&1; then
    echo "===== 安装成功 @ $(date '+%H:%M:%S') =====" >> "$LOG"
    exit 0
  fi
  echo "===== 第 $i 次失败，10 秒后重试 =====" >> "$LOG"
  sleep 10
done

echo "===== 重试全部失败 @ $(date '+%H:%M:%S') =====" >> "$LOG"
exit 1