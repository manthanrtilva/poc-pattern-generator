#!/usr/bin/env python3
"""Rainbow colors scrolling across 8 cells — animated TUI display."""

import sys
import time

RAINBOW = [
    (0x94, 0x00, 0xD3),  # Violet
    (0x4B, 0x00, 0x82),  # Indigo
    (0x00, 0x00, 0xFF),  # Blue
    (0x00, 0xFF, 0x00),  # Green
    (0xFF, 0xFF, 0x00),  # Yellow
    (0xFF, 0x7F, 0x00),  # Orange
    (0xFF, 0x00, 0x00),  # Red
]

CELL_WIDTH = 4  # width of each colored block in characters
DELAY = 0.03  # seconds between frames
CYCLE_DELAY = 3


def rgb_bg(r, g, b):
    """Return ANSI escape for 24-bit background color."""
    return f"\033[48;2;{r};{g};{b}m"

RESET = "\033[0m"

def main():
    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        opacity = 1
        rainbow_offset = 0
        going_up = True
        while True:
            line = "\033[H"
            # for led in range(8):
            #     r = (RAINBOW[(led + rainbow_offset) % 7][0] * opacity) / 100
            #     g = (RAINBOW[(led + rainbow_offset) % 7][1] * opacity) / 100
            #     b = (RAINBOW[(led + rainbow_offset) % 7][2] * opacity) / 100
            #     line += f"{rgb_bg(int(r), int(g), int(b))}{' ' * CELL_WIDTH}{RESET}"
            line += f"\n{RESET}Brightness: {opacity}%  Shift: {rainbow_offset}  (Ctrl+C to quit)\n"
            sys.stdout.write(line)
            sys.stdout.flush()

            if going_up:
                opacity += 1
                if opacity >= 100:
                    going_up = False
            else:
                opacity -= 1
                if opacity <= 1:
                    going_up = True
                    rainbow_offset += 1

            time.sleep(DELAY)
    except KeyboardInterrupt:
        pass
    finally:
        # Show cursor, clear screen
        sys.stdout.write("\033[?25h")
        sys.stdout.write("\033[0m\n")
        sys.stdout.flush()


if __name__ == "__main__":
    # Clear screen before starting
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()
    main()
