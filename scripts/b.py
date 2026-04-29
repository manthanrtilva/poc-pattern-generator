#!/usr/bin/env python3

# TUI application to display scrolling rainbow LEDs

import argparse
import sys
import time


def hue_to_rgb(hue):
    """Convert hue (0.0-1.0) to RGB (0-255) without colorsys.
    Hue maps to 6 sectors of 60° each:
      0/6: R=255, G rises    (red -> yellow)
      1/6: G=255, R falls    (yellow -> green)
      2/6: G=255, B rises    (green -> cyan)
      3/6: B=255, G falls    (cyan -> blue)
      4/6: B=255, R rises    (blue -> magenta)
      5/6: R=255, B falls    (magenta -> red)
    """
    h = (hue % 1.0) * 6.0
    sector = int(h)
    frac = h - sector  # 0.0 to 1.0 within the sector
    v = int(frac * 255)
    inv = 255 - v

    if sector == 0:   return (255, v,   0)
    elif sector == 1: return (inv, 255, 0)
    elif sector == 2: return (0,   255, v)
    elif sector == 3: return (0,   inv, 255)
    elif sector == 4: return (v,   0,   255)
    else:             return (255, 0,   inv)


def rgb_block(r, g, b):
    """Return a colored block using 24-bit ANSI escape codes."""
    return f"\033[48;2;{r};{g};{b}m  \033[0m"


def main():
    parser = argparse.ArgumentParser(description="TUI rainbow LED display")
    parser.add_argument("--leds", type=int, default=48, help="Number of LEDs")
    parser.add_argument("--delay", type=int, default=50, help="Delay in ms between frames")
    parser.add_argument("--speed", type=float, default=0.1, help="Hue shift per frame (smaller = smoother)")
    args = parser.parse_args()

    leds = args.leds
    delay = args.delay / 1000.0
    speed = args.speed

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        offset = 0.0
        while True:
            blocks = ""
            for i in range(leds):
                hue = (i + offset) / leds
                r, g, b = hue_to_rgb(hue)
                blocks += rgb_block(r, g, b)

            # Move to start of line and draw
            sys.stdout.write(f"\r{blocks}")
            sys.stdout.flush()

            offset += speed
            time.sleep(delay)
    except KeyboardInterrupt:
        pass
    finally:
        # Show cursor, reset
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
