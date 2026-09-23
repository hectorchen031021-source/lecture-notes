#!/usr/bin/env python3
"""Lecture Notes — 本地网页服务（0.1）
录音转写 + 文献提取 + 导出，全部本地运行。
"""
import json
import os
import re
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from faster_whisper import WhisperModel

BASE = Path(__file__).resolve().parent
SESSIONS_DIR = BASE / "sessions"
WEB_DIR = BASE / "web"
SESSIONS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Lecture Notes")

_models: dict[str, WhisperModel] = {}
_model_lock = threading.Lock()


def get_model(name: str) -> WhisperModel:
    with _model_lock:
        if name not in _models:
            _models[name] = WhisperModel(name, device="cpu", compute_type="int8")
        return _models[name]


# ---------- 会话 ----------

def session_dir(sid: str) -> Path:
    d = SESSIONS_DIR / sid
    d.mkdir(parents=True, exist_ok=True)
    return d


def safe_id(name: str) -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", name.strip()).strip("_") or "session"
    return f"{stamp}_{slug}"


def session_meta(sid: str) -> dict:
    d = session_dir(sid)
    meta_path = d / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    else:
        meta = {}
    transcript = (d / "transcript.md").read_text(encoding="utf-8") if (d / "transcript.md").exists() else ""
    lits = []
    lit_dir = d / "litterature"
    if lit_dir.exists():
        for f in sorted(lit_dir.iterdir()):
            if f.is_file() and not f.name.endswith(".txt"):
                txt = f.with_suffix(f.suffix + ".txt")
                lits.append({
                    "name": f.name,
                    "chars": len(txt.read_text(encoding="utf-8")) if txt.exists() else None,
                })
    return {
        "id": sid,
        "name": meta.get("name", sid),
        "created": meta.get("created", ""),
        "transcript": transcript,
        "literature": lits,
    }


@app.get("/api/sessions")
def list_sessions():
    items = []
    for d in sorted(SESSIONS_DIR.iterdir(), reverse=True):
        if d.is_dir() and (d / "meta.json").exists():
            items.append({"id": d.name, "name": json.loads((d / "meta.json").read_text(encoding="utf-8")).get("name", d.name)})
    return items


@app.post("/api/sessions")
def create_session(name: str = Form(...)):
    sid = safe_id(name)
    d = session_dir(sid)
    (d / "meta.json").write_text(json.dumps({"name": name, "created": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False), encoding="utf-8")
    (d / "transcript.md").write_text(f"# {name}\n\n", encoding="utf-8")
    return {"id": sid, "name": name}


@app.get("/api/sessions/{sid}")
def get_session(sid: str):
    return session_meta(sid)


# ---------- 转写 ----------

def save_temp_file(data: bytes, suffix: str) -> Path:
    import tempfile
    tmp = Path(tempfile.gettempdir()) / f"ln_chunk_{int(time.time()*1000)}{suffix}"
    tmp.write_bytes(data)
    return tmp


@app.post("/api/transcribe")
def transcribe(file: UploadFile = File(...), session_id: str = Form(""), model: str = Form("medium"), language: str = Form("fr"), save_audio: str = Form("")):
    data = file.file.read()
    name = (file.filename or "").lower()
    suffix = ".webm"
    if name.endswith(".mp4") or name.endswith(".m4a"):
        suffix = ".m4a"
    elif name.endswith(".wav"):
        suffix = ".wav"
    elif name.endswith(".ogg") or name.endswith(".opus"):
        suffix = ".ogg"
    tmp = save_temp_file(data, suffix)
    try:
        m = get_model(model)
        lang = None if language == "auto" else language
        segments, info = m.transcribe(str(tmp), language=lang, vad_filter=True, beam_size=5)
        text = "".join(s.strip() for s in (seg.text for seg in segments))
        if save_audio == "1" and session_id:
            import shutil
            d = session_dir(session_id)
            audio_dir = d / "audio"
            audio_dir.mkdir(exist_ok=True)
            shutil.copy(str(tmp), str(audio_dir / f"{time.strftime('%H%M%S')}.wav"))
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass

    if session_id:
        d = session_dir(session_id)
        tfile = d / "transcript.md"
        stamp = time.strftime("%H:%M")
        with open(tfile, "a", encoding="utf-8") as f:
            f.write(f"\n## {stamp}\n{text}\n")

    return {"text": text, "language": info.language}


# ---------- 文献 ----------

def extract_pdf(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    parts = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n".join(parts)


def extract_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def ocr_image(path: Path) -> str:
    import subprocess
    bin_path = BASE / "ocr"
    if not bin_path.exists():
        return ""
    try:
        r = subprocess.run([str(bin_path), str(path)], capture_output=True, text=True, timeout=120)
        return r.stdout.strip()
    except Exception:
        return ""


@app.post("/api/literature")
def upload_literature(file: UploadFile = File(...), session_id: str = Form("")):
    name = file.filename or "doc"
    lower = name.lower()
    d = session_dir(session_id) if session_id else SESSIONS_DIR / "_inbox"
    d.mkdir(parents=True, exist_ok=True)
    lit_dir = d / "litterature"
    lit_dir.mkdir(exist_ok=True)

    dest = lit_dir / name
    dest.write_bytes(file.file.read())

    text = ""
    if lower.endswith(".pdf"):
        text = extract_pdf(dest)
    elif lower.endswith(".docx"):
        text = extract_docx(dest)
    elif lower.endswith((".png", ".jpg", ".jpeg", ".tiff", ".tif", ".heic")):
        text = ocr_image(dest)
    elif lower.endswith(".txt") or lower.endswith(".md"):
        text = dest.read_text(encoding="utf-8", errors="ignore")
    else:
        return JSONResponse({"name": name, "chars": 0, "error": "不支持的类型（PDF / Word(.docx) / 图片 / txt）"}, status_code=400)

    if text.strip():
        dest.with_suffix(dest.suffix + ".txt").write_text(text, encoding="utf-8")

    return {"name": name, "chars": len(text.strip()), "error": None}


# ---------- 保存编辑后的转写 ----------

@app.post("/api/transcript")
def save_transcript(session_id: str = Form(...), text: str = Form(...)):
    d = session_dir(session_id)
    (d / "transcript.md").write_text(text, encoding="utf-8")
    return {"ok": True}


# ---------- 导出 ----------

@app.post("/api/export")
def export(session_id: str = Form(...), folder: str = Form("")):
    meta = session_meta(session_id)
    out = Path(folder).expanduser() if folder else (SESSIONS_DIR / session_id)
    out.mkdir(parents=True, exist_ok=True)

    transcript = meta["transcript"]
    (out / "transcript.md").write_text(transcript or "", encoding="utf-8")

    lit_dir = session_dir(session_id) / "litterature"
    if lit_dir.exists():
        for f in sorted(lit_dir.iterdir()):
            if f.is_file():
                (out / ("文献_" + f.name)).write_bytes(f.read_bytes())

    return {"folder": str(out), "transcript_chars": len(transcript)}


# ---------- 整理（LLM） ----------

DEFAULT_PROMPT = """你是课堂笔记助手。根据用户提供的【老师讲课转写】和【文献原文】，整理成结构化笔记。

要求：
1. 订正转写错误（最重要）：转写是语音识别的产物，含有大量错字。你必须【逐句订正】成通顺的原文语言（转写是什么语言就订正成什么语言），不得照抄原始错字。
2. 语言：笔记正文以【老师的原话/论点为主】——订正错误，但忠于老师讲的内容，不凭空添加老师没讲的观点。
3. 结构：用 Markdown，分小节（## 小节标题），每节正文段落式呈现老师论点。
4. 中文注解：每节下方加一行「中文要点：」一句话概括（中文）。
5. 文献引用：凡老师讲到、且【文献原文】里能找到的对应段落，在文末「Textes sources ／ 原文引用」用 > 引用块 + 出处引用；若文献里没有，标注出处。
6. 文末【必须】加「Vocabulaire ／ 词汇」表（术语 — 中文）和「Corrections ／ 转写订正」表（转写错 → 正确，至少列出订正过的主要条目）。
7. 开头加 YAML frontmatter：title、date、tags、subject、lang、status: 已整理、source: 课堂录音转写。
8. 只输出笔记 Markdown，不要多余解释。"""

SETTINGS_FILE = BASE / "settings.json"


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    return {
        "provider": "ollama",
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "llama3.2",
        "output_dir": "",
        "prompt": DEFAULT_PROMPT,
    }


@app.get("/api/settings")
def get_settings():
    return load_settings()


@app.post("/api/settings")
async def post_settings(request: Request):
    data = await request.json()
    s = load_settings()
    for k in ("provider", "base_url", "api_key", "model", "output_dir", "prompt"):
        if k in data:
            s[k] = data[k]
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    return s


def call_llm(base_url: str, api_key: str, model: str, messages, temperature: float = 0.3, timeout: int = 600, max_tokens: int = 6000) -> str:
    import urllib.request
    if base_url.strip().lower() in ("mock", "test") or api_key == "mock":
        return ("---\ntitle: 整理测试\ndate: 2026-09-23\ntags: [哲学]\nsubject: 哲学\nlang: fr\nstatus: 已整理\n---\n\n"
                "# Test ／ 测试\n\n## 1. Section de test · 测试节\n\nCeci est un résultat de test (mode mock), aucun modèle réel n'a été appelé.\n\n"
                "**中文要点**：这是 mock 模式测试输出。")
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps({"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"]


@app.post("/api/organize")
def organize(session_id: str = Form(...)):
    s = load_settings()
    meta = session_meta(session_id)
    transcript = meta["transcript"]

    lit_parts = []
    lit_dir = session_dir(session_id) / "litterature"
    if lit_dir.exists():
        for f in sorted(lit_dir.iterdir()):
            if f.is_file() and f.suffix == ".txt":
                lit_parts.append(f"### {f.name}\n{f.read_text(encoding='utf-8', errors='ignore')}")
    lit_text = "\n\n".join(lit_parts)

    user_msg = f"【老师讲课转写】\n{transcript}\n\n【文献原文】\n{lit_text}"
    from datetime import date
    sys_content = s.get("prompt", DEFAULT_PROMPT) + f"\n\n（今天是 {date.today().isoformat()}，frontmatter 的 date 字段用这个日期。）"
    messages = [
        {"role": "system", "content": sys_content},
        {"role": "user", "content": user_msg},
    ]
    try:
        base_url = s.get("base_url", "")
        if s.get("provider") == "mock":
            base_url = "mock"
        result = call_llm(base_url, s.get("api_key", ""), s.get("model", ""), messages)
    except Exception as e:
        return JSONResponse({"error": f"调用 LLM 失败：{e}"}, status_code=500)

    out_dir = Path(s.get("output_dir", "")).expanduser() if s.get("output_dir") else (session_dir(session_id) / "整理")
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"整理_{time.strftime('%Y%m%d_%H%M%S')}.md"
    (out_dir / fname).write_text(result, encoding="utf-8")
    return {"result": result, "saved": str(out_dir / fname)}


# ---------- 启动 ----------

app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


def _open_browser(port):
    time.sleep(1.0)
    webbrowser.open(f"http://127.0.0.1:{port}")


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "8765"))
    if os.environ.get("NO_BROWSER") != "1":
        threading.Thread(target=_open_browser, args=(port,), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
