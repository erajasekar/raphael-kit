#!/usr/bin/env python3
"""Binary display: type a decimal number and the LEDs show it in binary.

The rightmost LED is the 1s bit, the next is 2s, then 4s, 8s, 16s...
"""

from gpiozero import LED

# BCM GPIO numbers, in physical order along the LED bar (left to right)
LED_PINS = [18, 23, 24, 25, 8, 7, 12, 16, 20, 21]

MAX_VALUE = 16  # highest number accepted (16 needs 5 LEDs: 10000)

leds = [LED(pin) for pin in LED_PINS]
N = len(leds)


def show_binary(number):
    """Light the LEDs to match the binary form of number (right-aligned)."""
    bits = format(number, f"0{N}b")  # e.g. 5 -> '0000000101' for 10 LEDs
    for led, bit in zip(leds, bits):
        if bit == "1":
            led.on()
        else:
            led.off()
    # Text version of the LEDs in the terminal
    print("   " + " ".join("●" if b == "1" else "○" for b in bits))
    print(f"   {number} = {number:b} in binary")


def all_off():
    for led in leds:
        led.off()


print(f"Binary LED display. Enter a number from 0 to {MAX_VALUE}, or q to quit.")

try:
    while True:
        text = input("\nNumber: ").strip().lower()

        if text in ("q", "quit", "exit"):
            break

        if not text.isdigit():
            print(f"   Please enter a whole number from 0 to {MAX_VALUE}.")
            continue

        value = int(text)
        if value > MAX_VALUE:
            print(f"   Too big. The maximum is {MAX_VALUE}.")
            continue

        show_binary(value)

except (KeyboardInterrupt, EOFError):
    pass

finally:
    all_off()
    for led in leds:
        led.close()
    print("\nLEDs off. Bye!")
