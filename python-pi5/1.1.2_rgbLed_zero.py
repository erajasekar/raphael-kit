#!/usr/bin/env python3
from gpiozero import RGBLED
from time import sleep

# Define a list of (name, RGB color) pairs
COLORS = [
    ("Red", (1, 0, 0)),
    ("Green", (0, 1, 0)),
    ("Blue", (0, 0, 1)),
    ("Yellow", (1, 1, 0)),
    ("Magenta", (1, 0, 1)),
    ("Cyan", (0, 1, 1)),
    ("White", (1, 1, 1)),
    ("Orange", (1, 0.5, 0)),
    ("Purple", (0.5, 0, 1)),
    ("Spring Green", (0, 1, 0.5)),
    ("Lime", (0.5, 1, 0)),
    ("Azure", (0, 0.5, 1)),
    ("Rose", (1, 0, 0.5)),
    ("Periwinkle", (0.5, 0.5, 1)),
    ("Coral", (1, 0.3, 0.3)),
    ("Light Green", (0.3, 1, 0.3)),
    ("Soft Blue", (0.3, 0.3, 1)),
    ("Golden Yellow", (1, 0.7, 0)),
    ("Violet", (0.6, 0.2, 1)),
    ("Mint", (0.2, 1, 0.6))
]

# Initialize an RGB LED. Connect the red component to GPIO 17, green to GPIO 18, and blue to GPIO 27.
rgb_led = RGBLED(red=17, green=18, blue=27)

try:
    # Continuously cycle through the defined colors.
    while True:
        for name, color in COLORS:
            rgb_led.color = color
            print(f"Color set to: {name} {color}")
            sleep(1)

except KeyboardInterrupt:
    # Exit gracefully on Ctrl+C
    pass
