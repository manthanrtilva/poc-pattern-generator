#!/usr/bin/env python3

"""
Generate Mexican-wave frames with RLE-compressed binary output.

Binary format (RLE):
    [4 bytes leds      (u32 BE)]
    [4 bytes num_frames(u32 BE)]
    for each frame:
        RLE-encoded RGB data:
            [1 byte  run_length (1-255)]
            [3 bytes RGB (R, G, B)]
            ... repeats until `leds` pixels are decoded
        [4 bytes delay (u32 BE)]

The decoder reads RLE runs until it has accumulated `leds` pixels,
then reads the 4-byte delay. This is much more compact than the raw
format when many consecutive LEDs share the same colour (e.g. black).
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


def rle_encode_frame(colors):
    """RLE-encode a list of (R,G,B) tuples.

    Returns bytes: sequence of [count(1B), R(1B), G(1B), B(1B)] runs.
    """
    if not colors:
        return b""

    encoded = bytearray()
    cur = colors[0]
    count = 1

    for rgb in colors[1:]:
        if rgb == cur and count < 255:
            count += 1
        else:
            encoded.append(count)
            encoded.extend(cur)
            cur = rgb
            count = 1

    # flush last run
    encoded.append(count)
    encoded.extend(cur)
    return bytes(encoded)


def main():
    parser = argparse.ArgumentParser(description="Generate Mexican wave RLE-compressed binary.")
    parser.add_argument("--leds", "-l", type=int, default=8, help="Number of LEDs")
    parser.add_argument("--delay", "-d", type=int, default=1000, help="Delay per frame (ms)")
    parser.add_argument("--output", "-o", type=str, default="maxican_wave_rle.bin", help="Output file (binary)")
    parser.add_argument("--parts", "-p", type=int, default=1, help="Split output into N parts files")
    args = parser.parse_args()

    if args.leds < 1:
        raise SystemExit("leds must be >= 1")

    rows = simulate_frames(args.leds, args.delay)

    leds = args.leds
    parts = max(1, args.parts)
    base, ext = os.path.splitext(args.output)

    def write_bin(out_name, shard_leds, rows, start=0, end=None):
        if end is None:
            end = shard_leds
        with open(out_name, "wb") as f:
            # header
            f.write(shard_leds.to_bytes(4, "big"))
            f.write(len(rows).to_bytes(4, "big"))
            for row in rows:
                colors = row["a"][start:end]
                rle = rle_encode_frame(colors)
                f.write(rle)
                f.write(int(row["b"]).to_bytes(4, "big"))
        size = os.path.getsize(out_name)
        return size

    if parts == 1:
        size = write_bin(args.output, leds, rows, 0, leds)
        print(f"Wrote {args.output} ({size} bytes, {len(rows)} frames)")
    else:
        per_shard = (leds + parts - 1) // parts
        for i in range(parts):
            s = i * per_shard
            e = min(s + per_shard, leds)
            if s >= e:
                continue
            out_name = f"{base}.{i}{ext}"
            size = write_bin(out_name, e - s, rows, s, e)
            print(f"Wrote {out_name} ({size} bytes, {len(rows)} frames)")


if __name__ == "__main__":
    main()
