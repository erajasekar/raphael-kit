#!/usr/bin/env python3
"""Bouncing ball with real gravity.

A ball drops from one end, hits the "floor" at the other end, and bounces
lower and lower until it settles. Then it drops again from the opposite side.
It speeds up as it falls and hangs for a moment at the top of each bounce,
and the glowing trail comes from PWM brightness fading.
"""

from time import sleep

from gpiozero import PWMLED

# BCM GPIO numbers, in physical order along the LED bar (left to right)
LED_PINS = [18, 23, 24, 25, 8, 7, 12, 16, 20, 21]

GRAVITY = 70.0      # LEDs per second squared (higher = faster, snappier fall)
BOUNCE = 0.72       # energy kept per bounce (0.5 = dead ball, 0.9 = super bouncy)
MIN_SPEED = 7.0     # below this impact speed the ball stops bouncing
FADE = 0.72         # trail fade per frame (lower = shorter trail)
DT = 0.02           # seconds per frame (50 frames per second)
REST_TIME = 0.6     # pause after the ball settles

leds = [PWMLED(pin) for pin in LED_PINS]
N = len(leds)
TOP = N - 1         # starting height, in LED positions


def draw(height, flip):
    """Fade the old frame, then light the LED where the ball is now."""
    for led in leds:
        value = led.value * FADE
        led.value = value if value > 0.02 else 0
    position = round(height)
    if flip:
        position = N - 1 - position
    leds[position].value = 1.0


def one_drop(flip):
    """Drop the ball from the top and bounce it until it settles."""
    height = TOP
    speed = 0.0     # positive = moving up, negative = moving down
    while True:
        speed -= GRAVITY * DT
        height += speed * DT
        if height <= 0:
            height = 0
            if abs(speed) < MIN_SPEED:
                break
            speed = -speed * BOUNCE
        draw(height, flip)
        sleep(DT)

    # Ball has settled: let it rest on the floor, then fade out
    for _ in range(int(REST_TIME / DT)):
        draw(0, flip)
        sleep(DT)
    for _ in range(25):
        for led in leds:
            value = led.value * FADE
            led.value = value if value > 0.02 else 0
        sleep(DT)


try:
    flip = False
    while True:
        one_drop(flip)
        flip = not flip     # next drop comes from the other side

except KeyboardInterrupt:
    pass

finally:
    for led in leds:
        led.off()
        led.close()