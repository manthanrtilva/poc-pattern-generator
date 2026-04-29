#!/usr/bin/env python3

"""
Generate Mexican-wave frames and write a JSON file in the compact format:

{"a": NN, "b": [{"a": [0xRRGGBB,...], "b": NN}, ...]}

Where top-level `a` is `leds`, top-level `b` is `rows`, inside each row `a` is `colors`, and `b` is `delay`.
Colors are 24-bit integers (0xRRGGBB) per LED per frame. Output is minified JSON.
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
    parser.add_argument("--output", "-o", type=str, default="maxican_wave.json", help="Output JSON file")
    parser.add_argument("--parts", "-p", type=int, default=1, help="Split output into N oarts files (per-LED partition)")
    args = parser.parse_args()

    if args.leds < 1:
        raise SystemExit("leds must be >= 1")

    rows = simulate_frames(args.leds, args.delay)

    # If parts == 1, write a single compact file. If >1, split LEDs across parts
    # and write one file per shard containing only that shard's LED colors per row.
    leds = args.leds
    parts = max(1, args.parts)

    base, ext = os.path.splitext(args.output)
    if parts == 1:
        out = {"a": leds, "b": rows}
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, separators=(",", ":"))
        size = os.path.getsize(args.output)
        print(f"Wrote {args.output} ({size} bytes), frames: {len(rows)}")
    else:
        per_shard = (leds + parts - 1) // parts
        written = 0
        for i in range(parts):
            start = i * per_shard
            end = min(start + per_shard, leds)
            if start >= end:
                continue
            shard_rows = []
            for row in rows:
                colors = row.get("a", [])
                shard_colors = colors[start:end]
                shard_rows.append({"a": shard_colors, "b": row.get("b")})
            shard_out = {"a": end - start, "b": shard_rows}
            out_name = f"{base}.{i}{ext}"
            with open(out_name, "w", encoding="utf-8") as f:
                json.dump(shard_out, f, separators=(",", ":"))
            size = os.path.getsize(out_name)
            print(f"Wrote {out_name} ({size} bytes), frames: {len(shard_rows)}")
            written += 1
        if written == 0:
            print("No parts written (check --leds and --parts values)")


if __name__ == "__main__":
    main()
