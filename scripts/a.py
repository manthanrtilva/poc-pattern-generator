#!/usr/bin/python3

## Script to understand how much rows will be needed in maxican wave pattern

import argparse
import time

def main():
    parser = argparse.ArgumentParser(description="Calculate the number of rows needed for a maxican wave pattern.")
    parser.add_argument("--leds", type=int, help="Number of LEDs in the strip", default=8)
    parser.add_argument("--delay", type=int, help="Delay between each step in milliseconds", default=100)
    args = parser.parse_args()

    leds = args.leds
    if leds < 4:
        print("Number of LEDs must be at least 4 for a maxican wave pattern.")
        return
    delay = args.delay
    rows = [0] * leds
    add = [0] * leds
    rows[0] = 50
    rows[1] = 100
    rows[2] = 50
    add[0] = -1
    add[1] = -1
    add[2] = 1
    add[3] = 1
    forward = True
    counter = 0
    supper_counter = 0
    while True:
        rows = [x + y for x, y in zip(rows, add)]
        print(rows)
        counter = counter + 1
        supper_counter = supper_counter + 1
        if rows[0] == 50:
            print("Reached the end of the wave, total rows needed: ", supper_counter)
            break;
        if counter == 50:
            if rows[0] == 50:
                forward = True
                add = [0] * leds
                add[0] = -1
                add[1] = 1
                add[2] = 1
                add[leds - 1] = -1
            elif rows[leds-1] == 50:
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
        time.sleep(delay / 1000)
                




if __name__ == "__main__":
    main()