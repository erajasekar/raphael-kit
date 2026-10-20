#!/usr/bin/env python3
"""Pattern 3: lights start at both ends, collide in the middle, then explode outward."""

from gpiozero import LED
from time import sleep

# BCM GPIO numbers, in physical order along the LED bar (left to right)
LED_PINS = [18, 23, 24, 25, 8, 7, 12, 16, 20, 21]

DELAY = 0.15        # seconds per step (smaller = faster)
FLASH_TIME = 0.12   # how long the collision flash lasts

leds = [LED(pin) for pin in LED_PINS]
N = len(leds)
HALF = N // 2       # 5 steps from the edge to the center


def all_off():
    for led in leds:
        led.off()


def show(i):
    """Light the pair that is i steps in from each end."""
    all_off()
    leds[i].on()
    leds[N - 1 - i].on()


def collide():
    """Move both lights from the edges toward the center."""
    for i in range(HALF):
        show(i)
        sleep(DELAY)


def flash():
    """Quick burst when the two lights meet."""
    for _ in range(2):
        for led in leds:
            led.on()
        sleep(FLASH_TIME)
        all_off()
        sleep(FLASH_TIME)


def explode():
    """Send the two lights back out toward the edges."""
    # Stop at 1 because collide() starts at 0 on the next loop
    for i in range(HALF - 2, 0, -1):
        show(i)
        sleep(DELAY)


try:
    while True:
        collide()
        flash()
        explode()

except KeyboardInterrupt:
    pass

finally:
    all_off()
    for led in leds:
        led.close()
