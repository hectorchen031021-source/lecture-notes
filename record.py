#!/usr/bin/env python3
"""录音脚本：按 Ctrl+C 停止，保存为 WAV。"""
import argparse
import datetime
import os
import sys
import wave

import numpy as np
import sounddevice as sd


def main():
    p = argparse.ArgumentParser(description="录音并保存为 WAV（Ctrl+C 停止）")
    p.add_argument("--duration", type=float, default=0, help="录音秒数，0 表示直到 Ctrl+C")
    p.add_argument("--sample-rate", type=int, default=16000)
    p.add_argument("--device", type=int, default=None, help="输入设备编号，默认用系统默认")
    p.add_argument("--out", default=None, help="输出文件，默认带时间戳")
    args = p.parse_args()

    fs = args.sample_rate
    if args.out:
        out = args.out
    else:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = f"rec_{ts}.wav"

    print(f"开始录音（{fs} Hz）... 按 Ctrl+C 停止", file=sys.stderr)
    chunks = []

    try:
        with sd.InputStream(samplerate=fs, channels=1, dtype="float32",
                            device=args.device) as stream:
            while True:
                block, _ = stream.read(int(fs * 0.5))
                chunks.append(block.copy())
    except KeyboardInterrupt:
        print("\n停止录音，正在保存...", file=sys.stderr)

    if not chunks:
        print("没有录到任何内容。", file=sys.stderr)
        sys.exit(1)

    data = np.concatenate(chunks)
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)

    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(pcm.tobytes())

    secs = len(pcm) / fs
    print(f"已保存 {out}（{secs:.1f} 秒）")


if __name__ == "__main__":
    main()
