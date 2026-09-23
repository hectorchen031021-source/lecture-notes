#!/usr/bin/env python3
"""麦克风自检：录 3 秒，报告是否真的采集到声音。"""
import sys
import numpy as np
import sounddevice as sd


def main():
    print("可用输入设备：", file=sys.stderr)
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            mark = " <-- 默认" if i == sd.default.device[0] else ""
            print(f"  [{i}] {d['name']}{mark}", file=sys.stderr)

    fs = 16000
    print("\n正在录 3 秒，请对着麦克风说话...", file=sys.stderr)
    rec = sd.rec(int(fs * 3), samplerate=fs, channels=1, dtype="float32")
    sd.wait()
    peak = float(np.abs(rec).max())
    rms = float(np.sqrt(np.mean(rec ** 2)))
    print(f"\n峰值 peak = {peak:.4f}  均方根 rms = {rms:.4f}", file=sys.stderr)
    if peak < 0.02:
        print("结论：❌ 几乎没录到声音 → 麦克风权限没给这个终端，或选错了输入设备。", file=sys.stderr)
        print("      请到 系统设置 → 隐私与安全性 → 麦克风，勾选你用的终端（Terminal / iTerm）。", file=sys.stderr)
        sys.exit(1)
    else:
        print("结论：✅ 麦克风正常，能录到声音。", file=sys.stderr)


if __name__ == "__main__":
    main()
