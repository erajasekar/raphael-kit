#!/usr/bin/env python3
from gpiozero import RGBLED
from time import sleep
import colorsys

# Generate 100 vibrant colors using HSV to RGB conversion
COLORS = []
for i in range(100):
    hue = i / 100.0  # Evenly spaced hues around the color wheel
    saturation = 1.0  # Full saturation
    value = 1.0       # Full brightness
    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    COLORS.append((f"Color {i+1}", (r, g, b)))

# Initialize the RGB LED (adjust GPIO pins if needed)
rgb_led = RGBLED(red=17, green=18, blue=27)

try:
    while True:
        for name, color in COLORS:
            rgb_led.color = color
            #print(f"{name}: {tuple(round(c, 2) for c in color)}")
            sleep(0.1)

except KeyboardInterrupt:
    pass
