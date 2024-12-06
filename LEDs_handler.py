# LEDs_handler.py

import RPi.GPIO as GPIO
import time
import threading

# Configuración de pines
led_verde = 7
led_rojo = 12
rgb_pins = {'R': 16, 'G': 20, 'B': 21}

GPIO.setmode(GPIO.BCM)
GPIO.setup(led_verde, GPIO.OUT)
GPIO.setup(led_rojo, GPIO.OUT)
for pin in rgb_pins.values():
    GPIO.setup(pin, GPIO.OUT)

def clear_leds():
    GPIO.output(led_verde, GPIO.LOW)
    GPIO.output(led_rojo, GPIO.LOW)
    for pin in rgb_pins.values():
        GPIO.output(pin, GPIO.LOW)

def set_rgb_color(r, g, b):
    GPIO.output(rgb_pins['R'], GPIO.HIGH if r else GPIO.LOW)
    GPIO.output(rgb_pins['G'], GPIO.HIGH if g else GPIO.LOW)
    GPIO.output(rgb_pins['B'], GPIO.HIGH if b else GPIO.LOW)

def blink_rgb(r, g, b, stop_event, duration=0.5):
    while not stop_event.is_set():
        set_rgb_color(r, g, b)
        time.sleep(duration)
        set_rgb_color(0, 0, 0)
        time.sleep(duration)

def disco_mode(duration=5):
    start_time = time.time()
    while time.time() - start_time < duration:
        GPIO.output(led_verde, GPIO.HIGH)
        GPIO.output(led_rojo, GPIO.HIGH)
        set_rgb_color(1, 1, 1)
        time.sleep(0.1)
        GPIO.output(led_verde, GPIO.LOW)
        GPIO.output(led_rojo, GPIO.LOW)
        set_rgb_color(0, 0, 0)
        time.sleep(0.1)

def cleanup():
    clear_leds()
    GPIO.cleanup()
