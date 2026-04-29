#!/usr/bin/env python3

"""
Generate Mexican-wave frames with delta + palette compressed binary output.

Observation: the Mexican wave pattern has very high temporal redundancy —
only ~4 pixels change between consecutive frames, and there are very few
unique colours (≤255). This format exploits both properties.

Binary format (delta + palette):

  HEADER:
    [4 bytes  leds        (u32 BE)]
    [4 bytes  num_frames  (u32 BE)]
    [4 bytes  delay       (u32 BE)]   — constant delay for all frames
    [1 byte   palette_len (u8)]       — number of palette entries (0 means 256)
    [palette_len * 3 bytes]           — palette: R,G,B per entry

  KEYFRAME (frame 0):
    [1 byte  num_runs]
    for each run:
        [1 byte  run_length (1-255)]
        [1 byte  palette_index]
    (runs expand to `leds` pixels)

  DELTA FRAMES (frame 1 .. num_frames-1):
    [1 byte  num_changes (0-255)]
    for each change:
        [1 byte  led_index   (0-based)]
        [1 byte  palette_idx]

MCU decoder: keep a framebuffer of `leds` palette indices. Apply keyframe,
then for each delta just patch the changed indices and look up the palette.
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
    """Collect every unique (R,G,B) across all frames, return list + lookup dict."""
    colors = set()
    for row in rows:
        for c in row["a"]:
            colors.add(c)
    palette = sorted(colors)  # deterministic order; black (0,0,0) first
    if len(palette) > 256:
        raise ValueError(f"Too many unique colors ({len(palette)}); max 256 for 1-byte index")
    lookup = {c: i for i, c in enumerate(palette)}
    return palette, lookup


def rle_encode_indices(indices):
    """RLE-encode a list of palette indices.
    Returns bytes: [count(1B), index(1B)] runs.
    """
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


def main():
    parser = argparse.ArgumentParser(description="Generate Mexican wave delta+palette compressed binary.")
    parser.add_argument("--leds", "-l", type=int, default=8, help="Number of LEDs")
    parser.add_argument("--delay", "-d", type=int, default=1000, help="Delay per frame (ms)")
    parser.add_argument("--output", "-o", type=str, default="maxican_wave_delta.bin", help="Output file (binary)")
    parser.add_argument("--parts", "-p", type=int, default=1, help="Split output into N parts files")
    args = parser.parse_args()

    if args.leds < 1:
        raise SystemExit("leds must be >= 1")

    rows = simulate_frames(args.leds, args.delay)
    palette, lookup = build_palette(rows)

    leds = args.leds
    parts = max(1, args.parts)
    base, ext = os.path.splitext(args.output)

    def write_bin(out_name, shard_leds, rows, start=0, end=None):
        if end is None:
            end = start + shard_leds
        with open(out_name, "wb") as f:
            # --- HEADER ---
            f.write(shard_leds.to_bytes(4, "big"))
            f.write(len(rows).to_bytes(4, "big"))
            f.write(int(rows[0]["b"]).to_bytes(4, "big"))  # constant delay
            pal_len = len(palette) if len(palette) < 256 else 0  # 0 means 256
            f.write(pal_len.to_bytes(1, "big"))
            for r, g, b in palette:
                f.write(bytes([r, g, b]))

            # --- KEYFRAME (frame 0) ---
            indices = [lookup[c] for c in rows[0]["a"][start:end]]
            rle_bytes, num_runs = rle_encode_indices(indices)
            f.write(num_runs.to_bytes(1, "big"))
            f.write(rle_bytes)

            # --- DELTA FRAMES ---
            prev_indices = indices
            for row in rows[1:]:
                cur_indices = [lookup[c] for c in row["a"][start:end]]
                changes = []
                for j in range(shard_leds):
                    if cur_indices[j] != prev_indices[j]:
                        changes.append((j, cur_indices[j]))
                if len(changes) > 255:
                    raise ValueError(f"Too many changes in one frame ({len(changes)}); max 255")
                f.write(len(changes).to_bytes(1, "big"))
                for led_idx, pal_idx in changes:
                    f.write(bytes([led_idx, pal_idx]))
                prev_indices = cur_indices

        size = os.path.getsize(out_name)
        return size

    if parts == 1:
        size = write_bin(args.output, leds, rows, 0, leds)
        print(f"Wrote {args.output} ({size} bytes, {size/1024:.1f} KB, {len(rows)} frames, {len(palette)} palette entries)")
    else:
        per_shard = (leds + parts - 1) // parts
        for i in range(parts):
            s = i * per_shard
            e = min(s + per_shard, leds)
            if s >= e:
                continue
            out_name = f"{base}.{i}{ext}"
            size = write_bin(out_name, e - s, rows, s, e)
            print(f"Wrote {out_name} ({size} bytes, {size/1024:.1f} KB, {len(rows)} frames, {len(palette)} palette entries)")


if __name__ == "__main__":
    main()
