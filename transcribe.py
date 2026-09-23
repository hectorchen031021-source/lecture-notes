#!/usr/bin/env python3
"""转写脚本：把音频文件转成文字，输出到同名 .txt。"""
import argparse
import sys
import time

from faster_whisper import WhisperModel


def main():
    p = argparse.ArgumentParser(description="用 faster-whisper 把音频转成文字")
    p.add_argument("audio", help="音频文件路径（wav/mp3/m4a 等）")
    p.add_argument("--model", default="medium", help="模型：tiny/base/small/medium/large-v3")
    p.add_argument("--language", default="zh", help="语言：zh/ja/en/auto")
    p.add_argument("--out", default=None, help="输出 txt，默认同名 .txt")
    p.add_argument("--device", default="cpu", help="cpu 或 cuda")
    p.add_argument("--compute-type", default="int8", help="int8/float16/float32")
    args = p.parse_args()

    print(f"加载模型 {args.model} ...", file=sys.stderr)
    t0 = time.time()
    model = WhisperModel(args.model, device=args.device,
                         compute_type=args.compute_type)
    print(f"模型加载完成（{time.time()-t0:.1f}s），开始转写...", file=sys.stderr)

    lang = None if args.language == "auto" else args.language
    segments, info = model.transcribe(args.audio, language=lang,
                                      vad_filter=True, beam_size=5)

    out = args.out or (args.audio.rsplit(".", 1)[0] + ".md")
    lines = []
    for seg in segments:
        line = f"[{seg.start:7.1f} - {seg.end:7.1f}] {seg.text.strip()}"
        lines.append(line)
        print(line)

    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n已保存 {out}（{len(lines)} 段，检测语言 {info.language}）", file=sys.stderr)


if __name__ == "__main__":
    main()
