#!/usr/bin/python3

## Script to generate a scrolling rainbow pattern binary file
## Output format (RLE):
##   [leds: u32 BE]            number of LEDs
##   per row:
##     [rle_len: u16 BE]       length of RLE data
##     [rle_data: (count: u8, R: u8, G: u8, B: u8) ...]
##     [delay: u32 BE]         delay per frame (ms)

import argparse
import struct
import colorsys
import os


def hue_to_rgb(hue):
    """Convert hue (0.0-1.0) to (R, G, B) bytes."""
    r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def rle_encode_rgb(triplets):
    """RLE encode a list of (R,G,B) tuples. Returns bytes: [count, R, G, B] pairs."""
    if not triplets:
        return b""
    result = bytearray()
    current = triplets[0]
    count = 1
    for t in triplets[1:]:
        if t == current and count < 255:
            count += 1
        else:
            result.append(count)
            result.extend(current)
            current = t
            count = 1
    result.append(count)
    result.extend(current)
    return bytes(result)


def generate_frames(leds, delay):
    """Generate all rainbow frames. Each frame shifts the hue gradient by 1 LED."""
    # Build base rainbow: distribute hue evenly across all LEDs
    base_colors = [hue_to_rgb(i / leds) for i in range(leds)]

    frames = []
    for shift in range(leds):
        colors = base_colors[shift:] + base_colors[:shift]
        frames.append((colors, delay))
    return frames


def write_part(filename, leds_in_part, frames):
    """Write an RLE-encoded binary file for a part."""
    with open(filename, "wb") as f:
        f.write(struct.pack('>I', leds_in_part))
        for colors, delay in frames:
            rle_data = rle_encode_rgb(colors)
            f.write(struct.pack('>H', len(rle_data)))
            f.write(rle_data)
            f.write(struct.pack('>I', delay))
    return os.path.getsize(filename)


def main():
    parser = argparse.ArgumentParser(description="Generate a binary file for a scrolling rainbow pattern.")
    parser.add_argument("--leds", type=int, help="Total number of LEDs", default=48)
    parser.add_argument("--parts", type=int, help="Number of MCU parts to split into", default=1)
    parser.add_argument("--delay", type=int, help="Delay between each step in milliseconds", default=50)
    parser.add_argument("--output", type=str, help="Output file name", default="rainbow_pattern.bin")
    args = parser.parse_args()

    leds = args.leds
    parts = args.parts
    delay = args.delay
    output_file = args.output

    # Generate all frames with full LED count
    frames = generate_frames(leds, delay)

    base, ext = os.path.splitext(output_file)
    leds_per_part = leds // parts

    for p in range(parts):
        start = p * leds_per_part
        end = start + leds_per_part
        part_file = f"{base}_part{p + 1}{ext}" if parts > 1 else output_file

        # Slice each frame to this part's LED range
        part_frames = [(colors[start:end], d) for colors, d in frames]
        size = write_part(part_file, leds_per_part, part_frames)
        print(f"Part {p + 1}: LEDs {start}-{end - 1}, File: {part_file}, Size: {size} bytes")

    print(f"Total frames: {len(frames)}, Parts: {parts}")


if __name__ == "__main__":
    main()
