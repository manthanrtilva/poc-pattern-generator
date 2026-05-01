#!/usr/bin/env python3

"""
Generate scrolling-rainbow frames with rotation-based compression (v4).

This exploits the structure of the rainbow animation:
  - The pattern is a fixed palette that rotates by one LED per frame
  - No per-pixel deltas — only a global circular shift

Binary format:
  HEADER:
    [1 byte   format_id    (u8)]       — 1 = rainbow (rotation segments)
    [4 bytes  leds         (u32 BE)]
    [4 bytes  num_frames   (u32 BE)]   — total frames (for decoders that need it)
    [4 bytes  delay        (u32 BE)]   — constant delay for all frames
    [1 byte   palette_len  (u8)]       — 0 means 256
    [palette_len * 3 bytes]            — palette RGB entries

  KEYFRAME:
    [1 byte  num_runs]
    for each run:
        [1 byte  run_length (1-255)]
        [1 byte  palette_index]

  SEGMENTS:
    [1 byte  num_segments]
    for each segment:
        [1 byte  shift          (i8, two's complement: + = rotate left, - = rotate right)]
        [1 byte  repeat_count   (1-255)]

MCU decoder:
  1. Load palette and keyframe into framebuffer (palette indices).
  2. For each segment, repeat `repeat_count` times:
     - Rotate framebuffer by `shift` positions
       (positive shift = rotate left: fb = fb[shift:] + fb[:shift])
     - Render framebuffer using palette lookup, wait `delay` ms.
"""

import argparse
import colorsys
import os


def hue_to_rgb(hue):
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def simulate_frames(leds, delay):
    """Generate all rainbow frames. Each frame shifts the hue gradient by 1 LED."""
    base_colors = [hue_to_rgb(i / leds) for i in range(leds)]
    rows = []
    for shift in range(leds):
        colors = base_colors[shift:] + base_colors[:shift]
        rows.append({"a": colors, "b": delay})
    return rows


def build_palette(rows):
    """Collect every unique (R,G,B) across all frames, return sorted list + lookup."""
    colors = set()
    for row in rows:
        for c in row["a"]:
            colors.add(c)
    palette = sorted(colors)
    if len(palette) > 256:
        raise ValueError(f"Too many unique colors ({len(palette)}); max 256")
    lookup = {c: i for i, c in enumerate(palette)}
    return palette, lookup


def rle_encode_indices(indices):
    """RLE-encode palette indices. Returns (bytes, num_runs)."""
    if not indices:
        return b"", 0
    encoded = bytearray()
    cur = indices[0]
    count = 1
    num_runs = 0
    for idx in indices[1:]:
        if idx == cur and count < 255:
            count += 1
        else:
            encoded.append(count)
            encoded.append(cur)
            num_runs += 1
            cur = idx
            count = 1
    encoded.append(count)
    encoded.append(cur)
    num_runs += 1
    return bytes(encoded), num_runs


def detect_shift(prev, curr, leds):
    """Return integer shift s such that curr == prev[s:] + prev[:s], else None.

    Positive = rotate left, negative = rotate right. Range: (-leds/2, leds/2].
    """
    if prev == curr:
        return 0
    for s in range(1, leds):
        if curr == prev[s:] + prev[:s]:
            # Normalize to signed range so right-rotations encode as negative
            return s if s <= leds // 2 else s - leds
    return None


def build_segments(frames, leds):
    """Analyse delta frames and return list of (shift, repeat_count)."""
    segments = []
    cur_shift = None
    cur_count = 0

    prev = frames[0]
    for f in frames[1:]:
        s = detect_shift(prev, f, leds)
        if s is None:
            raise ValueError("Frame transition is not a pure rotation")
        if s == cur_shift and cur_count < 255:
            cur_count += 1
        else:
            if cur_shift is not None:
                segments.append((cur_shift, cur_count))
            cur_shift = s
            cur_count = 1
        prev = f

    if cur_shift is not None:
        segments.append((cur_shift, cur_count))

    return segments


def main():
    parser = argparse.ArgumentParser(description="Generate rainbow rotation-compressed binary (v4).")
    parser.add_argument("--leds", "-l", type=int, default=48, help="Number of LEDs")
    parser.add_argument("--delay", "-d", type=int, default=50, help="Delay per frame (ms)")
    parser.add_argument("--output", "-o", type=str, default="rainbow_v4.bin", help="Output file")
    args = parser.parse_args()

    if args.leds < 1:
        raise SystemExit("leds must be >= 1")

    rows = simulate_frames(args.leds, args.delay)
    print(rows)
    palette, lookup = build_palette(rows)
    leds = args.leds

    # Convert to palette-index frames
    frames = [[lookup[c] for c in row["a"]] for row in rows]
    segments = build_segments(frames, leds)

    # Verify: replay segments and compare to original frames
    fb = list(frames[0])
    frame_idx = 1
    for shift, count in segments:
        s = shift % leds
        for _ in range(count):
            fb = fb[s:] + fb[:s]
            assert fb == frames[frame_idx], f"Mismatch at frame {frame_idx}"
            frame_idx += 1
    assert frame_idx == len(frames), f"Frame count mismatch: {frame_idx} vs {len(frames)}"

    # Write binary
    with open(args.output, "wb") as f:
        # HEADER
        f.write(b"\x01")  # format_id: 1 = rainbow (rotation)
        f.write(leds.to_bytes(4, "big"))
        f.write(len(frames).to_bytes(4, "big"))
        f.write(args.delay.to_bytes(4, "big"))
        pal_len = len(palette) if len(palette) < 256 else 0
        f.write(pal_len.to_bytes(1, "big"))
        for r, g, b in palette:
            f.write(bytes([r, g, b]))

        # KEYFRAME (RLE of palette indices)
        rle_bytes, num_runs = rle_encode_indices(frames[0])
        f.write(num_runs.to_bytes(1, "big"))
        f.write(rle_bytes)

        # SEGMENTS
        f.write(len(segments).to_bytes(1, "big"))
        for shift, count in segments:
            f.write(shift.to_bytes(1, "big", signed=True))
            f.write(count.to_bytes(1, "big"))

    size = os.path.getsize(args.output)
    print(f"Wrote {args.output} ({size} bytes, {size/1024:.1f} KB)")
    print(f"  {len(frames)} frames, {len(palette)} palette entries, {len(segments)} segments")
    print(f"  Verification: OK")


if __name__ == "__main__":
    main()
