#!/usr/bin/env python3
from gpiozero import TonalBuzzer
from time import sleep

# Initialize a TonalBuzzer connected to GPIO pin 17
tb = TonalBuzzer(17)  # Update this pin number based on your setup

def play(tune):
    """
    Play a musical tune using the buzzer.
    :param tune: List of tuples (note, duration), where each tuple represents a note and its duration.
    """
    for note, duration in tune:
        print(note)  # Output the current note being played
        tb.play(note)  # Play the note on the buzzer
        sleep(float(duration))  # Delay for the duration of the note
    tb.stop()  # Stop playing after the tune is complete

# Define a musical tune as a sequence of notes and durations


tune = [
    ('C4', 0.4), ('C4', 0.4), ('G4', 0.4), ('G4', 0.4),
    ('A4', 0.4), ('A4', 0.4), ('G4', 0.8),
    ('F4', 0.4), ('F4', 0.4), ('E4', 0.4), ('E4', 0.4),
    ('D4', 0.4), ('D4', 0.4), ('C4', 0.8),

    ('G4', 0.4), ('G4', 0.4), ('F4', 0.4), ('F4', 0.4),
    ('E4', 0.4), ('E4', 0.4), ('D4', 0.8),
    ('G4', 0.4), ('G4', 0.4), ('F4', 0.4), ('F4', 0.4),
    ('E4', 0.4), ('E4', 0.4), ('D4', 0.8),

    ('C4', 0.4), ('C4', 0.4), ('G4', 0.4), ('G4', 0.4),
    ('A4', 0.4), ('A4', 0.4), ('G4', 0.8),
    ('F4', 0.4), ('F4', 0.4), ('E4', 0.4), ('E4', 0.4),
    ('D4', 0.4), ('D4', 0.4), ('C4', 0.8)
]





try:
    play(tune)  # Execute the play function to start playing the tune

except KeyboardInterrupt:
    # Handle KeyboardInterrupt for graceful termination
    pass

