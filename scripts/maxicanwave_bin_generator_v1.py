#!/usr/bin/env python3

"""
Generate Mexican-wave frames and write a binary file in the same stream format
used by handler_build_v1:

    [4 bytes leds (u32 BE)]
    for each row:
        [leds * 3 bytes RGB triplets (R,G,B)]
        [4 bytes delay (u32 BE)]

Top-level `leds` is the number of LEDs for the file/part. When `--parts` > 1
the script emits one binary file per part (base.0.bin, base.1.bin, ...). Colors
are 24-bit integers (0xRRGGBB). This produces the same byte stream that
`handler_build_v1` emits.
"""

import argparse
import json
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
            colors.append((r << 16) | (g << 8) | b)
        rows.append({"a": colors, "b": delay})

        cells = [c + a for c, a in zip(cells, add)]
        counter += 1

        if leds >= 3 and cells[0] == 50:
            colors = []
            for pct in cells:
                r = int(R * pct / 100)
                g = int(G * pct / 100)
                b = int(B * pct / 100)
                colors.append((r << 16) | (g << 8) | b)
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


def main():
    parser = argparse.ArgumentParser(description="Generate Mexican wave JSON frames.")
    parser.add_argument("--leds", "-l", type=int, default=8, help="Number of LEDs")
    parser.add_argument("--delay", "-d", type=int, default=1000, help="Delay per frame (ms)")
    parser.add_argument("--output", "-o", type=str, default="maxican_wave.bin", help="Output file (binary)")
    parser.add_argument("--parts", "-p", type=int, default=1, help="Split output into N parts files (per-LED partition)")
    args = parser.parse_args()

    if args.leds < 1:
        raise SystemExit("leds must be >= 1")

    rows = simulate_frames(args.leds, args.delay)

    # Write binary output matching handler_build_v1 stream
    leds = args.leds
    parts = max(1, args.parts)
    base, ext = os.path.splitext(args.output)
    if parts == 1:
        out_name = args.output
        with open(out_name, "wb") as f:
            # leds (u32 BE)
            f.write(args.leds.to_bytes(4, "big"))
            for row in rows:
                colors = row.get("a", [])
                for c in colors:
                    f.write(int(c).to_bytes(4, "big")[1:])
                f.write(int(row.get("b", 0)).to_bytes(4, "big"))
        size = os.path.getsize(out_name)
        print(f"Wrote {out_name} ({size} bytes), frames: {len(rows)}")
    else:
        per_shard = (leds + parts - 1) // parts
        written = 0
        for i in range(parts):
            start = i * per_shard
            end = min(start + per_shard, leds)
            if start >= end:
                continue
            out_name = f"{base}.{i}{ext}"
            with open(out_name, "wb") as f:
                f.write((end - start).to_bytes(4, "big"))
                for row in rows:
                    colors = row.get("a", [])
                    shard_colors = colors[start:end]
                    for c in shard_colors:
                        f.write(int(c).to_bytes(4, "big")[1:])
                    f.write(int(row.get("b", 0)).to_bytes(4, "big"))
            size = os.path.getsize(out_name)
            print(f"Wrote {out_name} ({size} bytes), frames: {len(rows)}")
            written += 1
        if written == 0:
            print("No parts written (check --leds and --parts values)")


if __name__ == "__main__":
    main()
