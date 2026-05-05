#!/usr/bin/env python3

"""
Generate scrolling-rainbow frames (v4).

Each LED has a single solid color from a 7-entry palette repeating along the
strip (LED i and LED i+7 share the same color). Each frame shifts the pattern
by one LED, so the animation has exactly PERIOD frames.

Because leds is a multiple of 8 (not of PERIOD), the strip cannot be expressed
as a pure rotation of itself, so we don't use rotation-segment compression.
Instead the binary just stores the palette; the decoder synthesises every LED
on the fly with `palette[(i - frame) mod PERIOD]`.

Binary format:
  [1 byte   format_id    (u8)]   — 2 = rainbow (palette-period synth)
  [4 bytes  leds         (u32 BE)]
  [4 bytes  num_frames   (u32 BE)]   — always PERIOD
  [4 bytes  delay        (u32 BE)]   — constant delay for all frames
  [1 byte   period       (u8)]
  [period * 3 bytes]                 — palette RGB entries

MCU decoder (pseudocode):
  for frame in 0..num_frames:
      for i in 0..leds:
          (r,g,b) = palette[(i - frame) mod period]
          set_led(i, r, g, b)
      delay_ms(delay)
"""

import argparse
import colorsys
import os
import struct


PERIOD = 7
FORMAT_ID = 1


def hue_to_rgb(hue):
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def build_palette():
    return [hue_to_rgb(i / PERIOD) for i in range(PERIOD)]


def main():
    parser = argparse.ArgumentParser(description="Generate rainbow palette-period binary (v4).")
    parser.add_argument("--leds", "-l", type=int, default=48, help="Number of LEDs (multiple of 8)")
    parser.add_argument("--delay", "-d", type=int, default=50, help="Delay per frame (ms)")
    parser.add_argument("--output", "-o", type=str, default="rainbow_v4.bin", help="Output file")
    args = parser.parse_args()

    if args.leds < 1:
        raise SystemExit("leds must be >= 1")
    if args.leds % 8 != 0:
        raise SystemExit("leds must be a multiple of 8")

    palette = build_palette()
    num_frames = PERIOD

    with open(args.output, "wb") as f:
        f.write(struct.pack(">B", FORMAT_ID))
        f.write(struct.pack(">I", args.leds))
        f.write(struct.pack(">I", num_frames))
        f.write(struct.pack(">I", args.delay))
        f.write(struct.pack(">B", PERIOD))
        for r, g, b in palette:
            f.write(bytes([r, g, b]))

    size = os.path.getsize(args.output)
    print(f"Wrote {args.output} ({size} bytes)")
    print(f"  leds={args.leds}, frames={num_frames}, delay={args.delay}ms, period={PERIOD}")
    print(f"  palette={palette}")


if __name__ == "__main__":
    main()
