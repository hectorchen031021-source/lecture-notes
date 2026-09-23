#!/usr/bin/env python3
"""边录边转写：按固定时长切片录音，每切完一段立刻转写，追加到同一份笔记。
听课过程中跑这个脚本即可，Ctrl+C 结束（未满一段也会转写当前已录内容）。
"""
import argparse
import datetime
import os
import signal
import sys
import wave

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


NOTES_DIR = os.environ.get("NOTES_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "notes"))


def write_wav(path, pcm, fs):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(pcm.tobytes())


def main():
    p = argparse.ArgumentParser(description="边录音边转写，实时生成笔记")
    p.add_argument("--model", default="medium", help="模型：tiny/base/small/medium/large-v3")
    p.add_argument("--language", default="fr", help="语言：fr/zh/ja/en/auto")
    p.add_argument("--chunk", type=float, default=30.0, help="每个切片的秒数")
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--device", type=int, default=None)
    p.add_argument("--out", default=None, help="笔记文件路径")
    p.add_argument("--keep-chunks", action="store_true", help="保留每段切片音频")
    args = p.parse_args()

    fs = args.sample_rate
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(NOTES_DIR, exist_ok=True)
    out = args.out or os.path.join(NOTES_DIR, f"philo_{ts}.md")
    chunk_dir = f"chunks_{ts}"
    if args.keep_chunks:
        os.makedirs(chunk_dir, exist_ok=True)

    print(f"加载模型 {args.model} ...", file=sys.stderr)
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    print("模型加载完成。开始监听，Ctrl+C 结束。\n", file=sys.stderr)

    lang = None if args.language == "auto" else args.language
    stop = False

    def on_sigint(sig, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, on_sigint)

    idx = 0
    with open(out, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f"title: 哲学講義 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("tags: [講義, 哲学]\n")
        f.write("---\n\n")

    with sd.InputStream(samplerate=fs, channels=1, dtype="float32",
                        device=args.device) as stream:
        while not stop:
            idx += 1
            frames = []
            need = int(fs * args.chunk)
            peak = 0.0
            collected = 0
            print(f"\n[第 {idx} 段] 录音中（约 {args.chunk:.0f}s，Ctrl+C 立即转写已录内容）...",
                  file=sys.stderr)
            while collected < need and not stop:
                block, _ = stream.read(int(fs * 0.2))
                frames.append(block.copy())
                collected += len(block)
                peak = max(peak, float(np.abs(block).max()))
                bars = int(min(peak * 50, 50))
                print(f"\r  音量 [{'#' * bars}{' ' * (50 - bars)}] {peak:.2f}",
                      end="", flush=True, file=sys.stderr)
            print(file=sys.stderr)

            if not frames:
                break

            data = np.concatenate(frames)
            pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
            secs = len(pcm) / fs

            if peak < 0.02:
                print("  ⚠ 几乎没有检测到声音：请检查麦克风权限或输入设备。",
                      file=sys.stderr)

            if args.keep_chunks:
                write_wav(os.path.join(chunk_dir, f"chunk_{idx:03d}.wav"), pcm, fs)

            print(f"[第 {idx} 段] 转写中（{secs:.1f}s）...", file=sys.stderr)
            tmp = os.path.join(os.environ.get("TMPDIR", "/tmp"), f"chunk_{idx}.wav")
            write_wav(tmp, pcm, fs)
            segments, _ = model.transcribe(tmp, language=lang,
                                           vad_filter=True, beam_size=5)
            text = "".join(s.strip() for s in (seg.text for seg in segments))

            stamp = datetime.datetime.now().strftime("%H:%M")
            block_out = f"## 第 {idx} 段（{stamp}）\n{text}\n"
            print(block_out)
            with open(out, "a", encoding="utf-8") as f:
                f.write(block_out + "\n")
            try:
                os.remove(tmp)
            except OSError:
                pass

    print(f"\n已结束，笔记保存在：{out}", file=sys.stderr)


if __name__ == "__main__":
    main()
