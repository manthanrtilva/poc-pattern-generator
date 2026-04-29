#!/usr/bin/python3

# script to optimise counter

import time

def main():
    TOTAL_CYCLE = 98 * 7  # 686 — full wrap period
    supper_counter = 0
    while True:
        counter = (supper_counter // 98) % 7
        up = (supper_counter % 98) < 49
        print(f"Counter: {counter}, Supper Counter: {supper_counter} up:{up}")
        for led in range(8):
            print(f"{led}: {(led+counter)%7} ", end=' ')
        print()
        supper_counter = (supper_counter + 1) % TOTAL_CYCLE
        time.sleep(0.05)
if __name__ == "__main__":
    main()