#!/usr/bin/env python3

"""
Generate Mexican-wave frames with delta-frame compression (v4).

Each frame is encoded as the per-LED palette-index changes vs. the previous
frame. Globally only 4 consecutive LEDs change per frame and the deltas are
±1, but when the strip is split into groups the global kernel may straddle a
group boundary, so a group sees 0–4 changes per frame. The delta layout
handles both cases uniformly.

Binary format (format_id = 0):
  HEADER:
    [1 byte   format_id    (u8)]       — 0
    [4 bytes  leds         (u32 BE)]
    [4 bytes  num_frames   (u32 BE)]
    [4 bytes  delay        (u32 BE)]   — constant delay for all frames
    [1 byte   palette_len  (u8)]       — 0 means 256
    [palette_len * 3 bytes]            — palette RGB entries

  KEYFRAME (RLE of palette indices):
    [1 byte  num_runs]
    for each run:
        [1 byte  run_length (1-255)]
        [1 byte  palette_index]

  DELTA FRAMES (RLE'd):
    [4 bytes  num_delta_frames (u32 BE)]   — = num_frames - 1
    [4 bytes  num_runs         (u32 BE)]
    for each run:
        [1 byte  repeat (1-255)]                — apply this delta `repeat` times
        [1 byte  num_changes (0-255)]
        for each change:
            [1 byte  led_idx (0..leds-1)]
            [1 byte  delta   (i8, typically ±1)]

MCU decoder:
  1. Load palette + keyframe into framebuffer (palette indices).
  2. For each run, repeat `repeat` times: apply the change list (fb[led] += d),
     render via palette lookup, wait `delay` ms.
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


def write_pattern(path, group_leds, group_frames, palette, delay):
    """Write a delta-frame compressed file (format_id = 0).

    Delta records are RLE-compressed: consecutive frames whose change-set is
    identical are stored once with a repeat count. This is highly effective
    for the wave pattern, where the same ±1 kernel is applied to the same
    LEDs for many frames between kernel rotations.
    """
    with open(path, "wb") as f:
        f.write(b"\x00")
        f.write(group_leds.to_bytes(4, "big"))
        f.write(len(group_frames).to_bytes(4, "big"))
        f.write(delay.to_bytes(4, "big"))
        pal_len = len(palette) if len(palette) < 256 else 0
        f.write(pal_len.to_bytes(1, "big"))
        for r, g, b in palette:
            f.write(bytes([r, g, b]))

        rle_bytes, num_runs = rle_encode_indices(group_frames[0])
        f.write(num_runs.to_bytes(1, "big"))
        f.write(rle_bytes)

        # Compute per-frame change-sets
        all_changes = []
        prev = group_frames[0]
        for cur in group_frames[1:]:
            changes = tuple(
                (j, cur[j] - prev[j]) for j in range(group_leds) if cur[j] != prev[j]
            )
            if len(changes) > 255:
                raise ValueError(f"Too many changes in one frame: {len(changes)}")
            all_changes.append(changes)
            prev = cur

        # RLE-collapse identical consecutive change-sets (cap repeat at 255)
        runs = []  # list of (repeat, changes)
        for ch in all_changes:
            if runs and runs[-1][1] == ch and runs[-1][0] < 255:
                runs[-1] = (runs[-1][0] + 1, ch)
            else:
                runs.append((1, ch))

        num_delta = len(all_changes)
        f.write(num_delta.to_bytes(4, "big"))
        f.write(len(runs).to_bytes(4, "big"))
        for repeat, changes in runs:
            f.write(repeat.to_bytes(1, "big"))
            f.write(len(changes).to_bytes(1, "big"))
            for j, d in changes:
                f.write(j.to_bytes(1, "big"))
                f.write(int(d).to_bytes(1, "big", signed=True))

    return os.path.getsize(path), len(runs)


def parse_groups(spec, total_leds):
    """Parse --groups: an int N (split into N equal groups) or a comma-separated
    list of explicit group sizes (e.g. "24,8"). Each group size must be a
    positive multiple of 8, and the sizes must sum to total_leds."""
    spec = spec.strip()
    if "," in spec:
        sizes = [int(x) for x in spec.split(",") if x.strip()]
    else:
        n = int(spec)
        if n < 1:
            raise SystemExit("groups must be >= 1")
        if total_leds % n != 0:
            raise SystemExit(f"leds ({total_leds}) must be divisible by groups ({n})")
        sizes = [total_leds // n] * n

    for s in sizes:
        if s < 1:
            raise SystemExit(f"group size must be >= 1 (got {s})")
        # if s % 8 != 0:
        #     raise SystemExit(f"group size must be a multiple of 8 (got {s})")
    if sum(sizes) != total_leds:
        raise SystemExit(f"group sizes {sizes} sum to {sum(sizes)}, expected {total_leds}")
    return sizes


def main():
    parser = argparse.ArgumentParser(description="Generate Mexican wave delta-compressed binary (v4).")
    parser.add_argument("--leds", "-l", type=int, default=8, help="Total number of LEDs across all groups")
    parser.add_argument("--delay", "-d", type=int, default=1000, help="Delay per frame (ms)")
    parser.add_argument("--output", "-o", type=str, default="maxican_wave_v4.bin",
                        help="Output file (single-group) or base name (multi-group, gets -gN suffix)")
    parser.add_argument("--groups", "-g", type=str, default="1",
                        help="Either an integer N (split into N equal groups) or a "
                             "comma-separated list of group sizes (e.g. '24,8'). "
                             "Each group size must be a multiple of 8.")
    args = parser.parse_args()

    if args.leds < 1:
        raise SystemExit("leds must be >= 1")

    group_sizes = parse_groups(args.groups, args.leds)

    rows = simulate_frames(args.leds, args.delay, base_color=(0, 255, 0))
    palette, lookup = build_palette(rows)
    frames = [[lookup[c] for c in row["a"]] for row in rows]

    if len(group_sizes) == 1:
        print("frames",frames)
        print("palette",palette)
        size, num_runs = write_pattern(args.output, args.leds, frames, palette, args.delay)
        print(f"Wrote {args.output} ({size} bytes, {size/1024:.1f} KB)")
        print(f"  {len(frames)} frames, {len(palette)} palette entries, {num_runs} delta runs")
        return

    base, ext = os.path.splitext(args.output)
    if not ext:
        ext = ".bin"

    print(f"Splitting {args.leds} LEDs into {len(group_sizes)} groups: {group_sizes}")
    lo = 0
    for g, gs in enumerate(group_sizes):
        hi = lo + gs
        group_frames = [frame[lo:hi] for frame in frames]
        path = f"{base}-g{g}{ext}"
        size, num_runs = write_pattern(path, gs, group_frames, palette, args.delay)
        print(f"  group {g} (leds {lo}..{hi-1}, size {gs}): wrote {path} ({size} bytes, {num_runs} runs)")
        lo = hi


if __name__ == "__main__":
    main()
