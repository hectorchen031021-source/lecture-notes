#!/bin/zsh
# 一键安装：创建虚拟环境、装依赖、编译 OCR 组件
set -e
cd "$(dirname "$0")"

echo "==> 创建虚拟环境"
python3 -m venv .venv

echo "==> 安装依赖"
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo "==> 编译 OCR（macOS Vision，可选）"
if command -v swiftc >/dev/null 2>&1; then
  swiftc -O ocr.swift -o ocr && echo "OCR 编译完成"
else
  echo "未找到 swiftc，跳过 OCR 编译（图片文献识别不可用，其余功能正常）"
fi

echo ""
echo "完成！双击 启动.command 即可运行，浏览器会自动打开 http://127.0.0.1:8765"
