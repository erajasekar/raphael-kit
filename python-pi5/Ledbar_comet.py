#!/usr/bin/env python3
"""Pattern 2: a bouncing comet with a fading tail (uses PWM for brightness)."""

from collections import deque
from itertools import cycle
from time import sleep

from gpiozero import PWMLED

# BCM GPIO numbers, in physical order along the LED bar (left to right)
LED_PINS = [18, 23, 24, 25, 8, 7, 12, 16, 20, 21]

DELAY = 0.08  # seconds per step (smaller = faster)

# Brightness of the head, then each tail LED behind it (0.0 to 1.0).
# Uneven steps look smoother because our eyes judge brightness on a curve.
# Add more values for a longer tail, e.g. [1.0, 0.4, 0.15, 0.06, 0.02]
TAIL = [1.0, 0.3, 0.1, 0.03]

leds = [PWMLED(pin) for pin in LED_PINS]
N = len(leds)

# Head path: 0 -> 9 -> back down to 1, then repeats (no double-hit at the ends)
path = list(range(N)) + list(range(N - 2, 0, -1))

# Remembers the last few head positions, newest first
trail = deque(maxlen=len(TAIL))


def all_off():
    for led in leds:
        led.value = 0


try:
    for head in cycle(path):
        trail.appendleft(head)
        all_off()
        for pos, brightness in zip(trail, TAIL):
            # max() handles the turnaround, where one LED can appear twice
            leds[pos].value = max(leds[pos].value, brightness)
        sleep(DELAY)

except KeyboardInterrupt:
    pass

finally:
    all_off()
    for led in leds:
        led.close()
