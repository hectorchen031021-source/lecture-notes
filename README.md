# Lecture Notes

本地、隐私优先的课堂笔记工具：**录音 → 转写 → 上传文献 → AI 整理 → 导出 Obsidian**，全程离线（转写在本地，AI 整理可选本地 Ollama 或你自带的 API key）。

A local, privacy-first lecture-note tool: record → transcribe → attach readings → AI-organize → export to Obsidian.

## 功能 Features

- 🎙️ 浏览器录音，每 30 秒自动转写（本地 faster-whisper，支持法语/中文/日语等）
- 📄 文献上传：PDF / Word 自动提取文字；图片（截图/扫描）用 macOS Vision 做 OCR
- 🤖 一键 AI 整理：法语为主的哲学课结构化笔记（订正转写错字、原文引用、词汇表、订正表）
- 🔌 可插拔 LLM：本地 Ollama 或任意 OpenAI 兼容 API（DeepSeek / 硅基流动 / Gemini / OpenAI）
- 🗂️ 多课程会话管理、转写可编辑、保存原始音频
- 📤 导出 Markdown 到任意文件夹（可指向 Obsidian 库）

## 系统要求 Requirements

- **macOS**（图片 OCR 依赖 macOS Vision；录音用浏览器 API）
- Python 3.10+
- 首次转写会下载 Whisper 模型（medium 约 1.5 GB，仅一次，之后离线）

## 快速开始 Quick start

```bash
git clone <你的仓库地址>
cd lecture-notes
./setup.sh          # 创建虚拟环境 + 装依赖 + 编译 OCR
./启动.command       # 启动服务，自动打开浏览器 http://127.0.0.1:8765
```

或者手动：

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
swiftc -O ocr.swift -o ocr        # 可选，macOS 图片 OCR
./.venv/bin/python server.py
```

## 使用 Usage

1. 首次打开，给课程起个名字。
2. 点录音键开始；每 30 秒自动出一段转写；可点转写文字直接改错字，点「保存转写修改」。
3. 文献区上传教授发的 PDF/Word/图片，或填「书名+章节」出处。
4. 右侧「整理笔记（LLM）」：选后端、填模型，点「整理」→ 生成结构化笔记。

## 整理（AI）配置 Configuration

整理需要一个大模型。两种方式（在网页「整理笔记」卡片里设置，保存后写入 `settings.json`）：

| 后端 | 说明 |
| --- | --- |
| 本地 Ollama | 免费全隐私；先 `brew install ollama` 并 `ollama pull llama3.2`，然后填 `http://localhost:11434/v1`、模型名 |
| 云端 API | 任意 OpenAI 兼容接口。例如硅基流动：base_url `https://api.siliconflow.cn/v1`，模型 `deepseek-ai/DeepSeek-V4-Flash`，key 填你的 |

> `settings.json`（含 API key）已在 `.gitignore` 中，不会被提交。

## 隐私 Privacy

转写、文献提取、OCR 全部在**本地**运行，音频与文字不上传。只有「AI 整理」这一步会把文字发给你在设置里指定的 LLM 服务（用本地 Ollama 则完全不出设备）。

## 项目结构 Structure

```
server.py        后端（FastAPI）：转写 / 文献提取 / OCR / 整理 / 导出 API
web/index.html   前端（录音、文献、整理界面）
ocr.swift        macOS 图片 OCR（Vision），setup.sh 会编译成 ocr
setup.sh         一键安装
requirements.txt 依赖
sessions/        会话数据（录音转写、文献，运行生成，已 gitignore）
```

## License

MIT
