#!/usr/bin/env python3
"""Pattern 5: marquee chase. Every third LED is on and the pattern slides along."""

from time import sleep

from gpiozero import LED

# BCM GPIO numbers, in physical order along the LED bar (left to right)
LED_PINS = [18, 23, 24, 25, 8, 7, 12, 16, 20, 21]

DELAY = 0.15    # seconds per step (smaller = faster)
SPACING = 3     # one LED on out of every SPACING (3 = ●○○●○○●○○●)
DIRECTION = 1   # 1 = slide left to right, -1 = right to left

leds = [LED(pin) for pin in LED_PINS]
N = len(leds)


def all_off():
    for led in leds:
        led.off()


def show(offset):
    """Turn on every SPACING-th LED, starting at offset."""
    line = ""
    for i, led in enumerate(leds):
        if (i - offset) % SPACING == 0:
            led.on()
            line += "●"
        else:
            led.off()
            line += "○"
    print(line)  # text preview in the terminal


try:
    offset = 0
    while True:
        show(offset)
        offset = (offset + DIRECTION) % SPACING
        sleep(DELAY)

except KeyboardInterrupt:
    pass

finally:
    all_off()
    for led in leds:
        led.close()