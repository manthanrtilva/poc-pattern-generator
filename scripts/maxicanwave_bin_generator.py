#!/usr/bin/python3

## Script to generate the Mexican wave pattern binary file
## Output format (version 0x02 — repeat-delta):
##   [0x02]                    version
##   [leds: u32 BE]            number of LEDs
##   [R: u8, G: u8, B: u8]    base color
##   [num_init: u8][(index: u8, value: u8) × num_init]  initial non-zero cells (percentage 0-100)
##   segments until EOF:
##     [repeat: u16 BE]        frames to generate with this delta
##     [delay: u32 BE]         delay per frame (ms)
##     [num_deltas: u8]        number of LEDs changing per frame
##     [(index: u8, delta: i8) × num_deltas]

import argparse
import struct

def main():
    parser = argparse.ArgumentParser(description="Generate a binary file for the Mexican wave pattern.")
    parser.add_argument("--leds", type=int, help="Number of LEDs in the strip", default=16)
    parser.add_argument("--parts", type=int, help="Number of parts of led groups", default=2)
    parser.add_argument("--delay", type=int, help="Delay between each step in milliseconds", default=100)
    parser.add_argument("--output", type=str, help="Output file name", default="maxican_wave_pattern.bin")
    args = parser.parse_args()

    output_file = args.output
    leds = args.leds
    delay = args.delay
    if leds < 4:
        print("Number of LEDs must be at least 4 for a maxican wave pattern.")
        return

    R = 0xFF
    G = 0x00
    B = 0x00

    # Initial cell percentages (0-100)
    cells = [0] * leds
    cells[0] = 50
    cells[1] = 100
    cells[2] = 50

    # Initial add vector
    add = [0] * leds
    add[0] = -1
    add[1] = -1
    add[2] = 1
    add[3] = 1

    # Collect segments: (repeat_count, delay, [(index, delta), ...])
    segments = []
    forward = True
    counter = 0
    total_frames = 0

    while True:
        # Apply add for this frame
        cells = [c + a for c, a in zip(cells, add)]
        counter += 1
        total_frames += 1

        if cells[0] == 50:
            # Wave completed full cycle
            # Get non-zero deltas for current add vector
            deltas = [(i, add[i]) for i in range(leds) if add[i] != 0]
            segments.append((counter, delay, deltas))
            break

        if counter == 50:
            # Save current segment
            deltas = [(i, add[i]) for i in range(leds) if add[i] != 0]
            segments.append((counter, delay, deltas))

            # Update add vector
            if cells[0] == 50:
                forward = True
                add = [0] * leds
                add[0] = -1
                add[1] = 1
                add[2] = 1
                add[leds - 1] = -1
            elif cells[leds-1] == 50:
                forward = False
                add = [0] * leds
                add[0] = -1
                add[leds - 3] = 1
                add[leds - 2] = 1
                add[leds - 1] = -1
            if forward:
                add = [add[leds-1]] + add[:-1]
            else:
                add = add[1:] + [add[0]]
            counter = 0

    # Write binary — split into parts
    parts = args.parts
    leds_per_part = leds // parts
    init_cells = [(0, 50), (1, 100), (2, 50)]

    import os
    base, ext = os.path.splitext(output_file)

    for p in range(parts):
        start = p * leds_per_part
        end = start + leds_per_part
        part_file = f"{base}_part{p + 1}{ext}" if parts > 1 else output_file

        # Filter and remap init cells for this part
        part_init = [(idx - start, val) for idx, val in init_cells if start <= idx < end]

        with open(part_file, "wb") as f:
            f.write(struct.pack('B', 0x02))
            f.write(struct.pack('>I', leds_per_part))
            f.write(struct.pack('BBB', R, G, B))
            f.write(struct.pack('B', len(part_init)))
            for idx, val in part_init:
                f.write(struct.pack('BB', idx, val))
            for repeat, seg_delay, deltas in segments:
                # Filter and remap deltas for this part
                part_deltas = [(idx - start, delta) for idx, delta in deltas if start <= idx < end]
                f.write(struct.pack('>H', repeat))
                f.write(struct.pack('>I', seg_delay))
                f.write(struct.pack('B', len(part_deltas)))
                for idx, delta in part_deltas:
                    f.write(struct.pack('Bb', idx, delta))

        size = os.path.getsize(part_file)
        print(f"Part {p + 1}: LEDs {start}-{end - 1}, File: {part_file}, Size: {size} bytes")

    print(f"Total frames: {total_frames}, Segments: {len(segments)}, Parts: {parts}")

if __name__ == "__main__":
    main()
