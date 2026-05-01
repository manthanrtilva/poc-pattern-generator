#!/usr/bin/env python3

"""
Generate Mexican-wave frames with segment-based compression (v4).

This exploits the structure of the wave animation:
  - Only 4 consecutive LEDs change per frame
  - Palette index deltas are always ±1
  - The "add kernel" slides across the strip in predictable segments

Binary format:
  HEADER:
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
        [1 byte  start_led]       — first LED index of the 4-LED kernel
        [1 byte  repeat_count]    — how many frames this segment lasts
        [1 byte  flags]           — bit 0: sign pattern (0 = -1,-1,+1,+1  1 = +1,+1,-1,-1)

MCU decoder:
  1. Load palette and keyframe into framebuffer (palette indices).
  2. For each segment, repeat `repeat_count` times:
     - Apply the 4-pixel kernel at `start_led` with the given sign pattern:
       fb[start_led+0] += sign[0]   (i.e. ±1 to palette index)
       fb[start_led+1] += sign[1]
       fb[start_led+2] += sign[2]
       fb[start_led+3] += sign[3]
     - Render framebuffer using palette lookup, wait `delay` ms.
"""

import argparse
import os


def simulate_frames(leds, delay, base_color=(255, 0, 0)):
    R, G, B = base_color
    cells = [0] * leds
    if leds >= 3:
        cells[0] = 50
        cells[1] = 100
        cells[2] = 50

    add = [0] * leds
    if leds >= 4:
        add[0] = -1
        add[1] = -1
        add[2] = 1
        add[3] = 1

    rows = []
    forward = True
    counter = 0

    while True:
        colors = []
        for pct in cells:
            r = int(R * pct / 100)
            g = int(G * pct / 100)
            b = int(B * pct / 100)
            colors.append((r, g, b))
        rows.append({"a": colors, "b": delay})

        cells = [c + a for c, a in zip(cells, add)]
        counter += 1

        if leds >= 3 and cells[0] == 50:
            colors = []
            for pct in cells:
                r = int(R * pct / 100)
                g = int(G * pct / 100)
                b = int(B * pct / 100)
                colors.append((r, g, b))
            rows.append({"a": colors, "b": delay})
            break

        if counter >= 10000:
            break

        if counter % 50 == 0:
            if leds >= 3 and cells[0] == 50:
                forward = True
                add = [0] * leds
                if leds >= 4:
                    add[0] = -1
                    add[1] = 1
                    add[2] = 1
                    add[leds - 1] = -1
            elif leds >= 1 and cells[leds - 1] == 50:
                forward = False
                add = [0] * leds
                if leds >= 4:
                    add[0] = -1
                    add[leds - 3] = 1
                    add[leds - 2] = 1
                    add[leds - 1] = -1
            if forward:
                add = [add[leds - 1]] + add[:-1]
            else:
                add = add[1:] + [add[0]]

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


def build_segments(frames, leds):
    """Analyse delta frames and return list of (start_led, repeat_count, flags).

    flags bit 0: 0 = kernel (-1,-1,+1,+1), 1 = kernel (+1,+1,-1,-1)
    """
    SIGN_FWD = (-1, -1, 1, 1)
    SIGN_BWD = (1, 1, -1, -1)

    prev = frames[0]
    segments = []
    cur_key = None   # (start_led, flags)
    cur_count = 0

    for f in frames[1:]:
        positions = [j for j in range(leds) if f[j] != prev[j]]
        if len(positions) == 4 and positions == list(range(positions[0], positions[0] + 4)):
            signs = tuple(1 if f[j] > prev[j] else -1 for j in positions)
            start = positions[0]
            if signs == SIGN_FWD:
                flags = 0
            elif signs == SIGN_BWD:
                flags = 1
            else:
                raise ValueError(f"Unexpected sign pattern: {signs}")
            key = (start, flags)
            if key == cur_key and cur_count < 255:
                cur_count += 1
            else:
                if cur_key is not None:
                    segments.append((cur_key[0], cur_count, cur_key[1]))
                cur_key = key
                cur_count = 1
        else:
            # Fallback: shouldn't happen for Mexican wave
            raise ValueError(f"Non-4-consecutive delta at positions {positions}")
        prev = f

    if cur_key is not None:
        segments.append((cur_key[0], cur_count, cur_key[1]))

    return segments


def main():
    parser = argparse.ArgumentParser(description="Generate Mexican wave segment-compressed binary (v4).")
    parser.add_argument("--leds", "-l", type=int, default=8, help="Number of LEDs")
    parser.add_argument("--delay", "-d", type=int, default=1000, help="Delay per frame (ms)")
    parser.add_argument("--output", "-o", type=str, default="maxican_wave_v4.bin", help="Output file")
    args = parser.parse_args()

    if args.leds < 1:
        raise SystemExit("leds must be >= 1")

    rows = simulate_frames(args.leds, args.delay, base_color=(0, 255, 0))
    palette, lookup = build_palette(rows)
    leds = args.leds

    # Convert to palette-index frames
    frames = [[lookup[c] for c in row["a"]] for row in rows]
    segments = build_segments(frames, leds)

    # Verify: replay segments and compare to original frames
    fb = list(frames[0])
    frame_idx = 1
    for start, count, flags in segments:
        kernel = [-1, -1, 1, 1] if flags == 0 else [1, 1, -1, -1]
        for _ in range(count):
            for k in range(4):
                fb[start + k] += kernel[k]
            assert fb == frames[frame_idx], f"Mismatch at frame {frame_idx}"
            frame_idx += 1
    assert frame_idx == len(frames), f"Frame count mismatch: {frame_idx} vs {len(frames)}"

    # Write binary
    with open(args.output, "wb") as f:
        # HEADER
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
        for start, count, flags in segments:
            f.write(bytes([start, count, flags]))

    size = os.path.getsize(args.output)
    print(f"Wrote {args.output} ({size} bytes, {size/1024:.1f} KB)")
    print(f"  {len(frames)} frames, {len(palette)} palette entries, {len(segments)} segments")
    print(f"  Verification: OK")


if __name__ == "__main__":
    main()
