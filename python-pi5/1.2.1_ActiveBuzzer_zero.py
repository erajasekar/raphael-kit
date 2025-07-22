#!/usr/bin/env python3
from gpiozero import Buzzer
from time import sleep

# Initialize a Buzzer object on GPIO pin 17
buzzer = Buzzer(17)

try:
    while True:
        # Turn on the buzzer
        print('Buzzer On')
        buzzer.on()
        sleep(1.0)  # Keep the buzzer on for 0.1 seconds

        # Turn off the buzzer
        print('Buzzer Off')
        buzzer.off()
        sleep(1.0)  # Keep the buzzer off for 0.1 seconds

except KeyboardInterrupt:
    # Handle KeyboardInterrupt (Ctrl+C) for clean script termination
    pass
