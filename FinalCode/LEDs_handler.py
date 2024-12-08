import RPi.GPIO as GPIO
import time
import threading

class LEDHandler:
    def __init__(self):
        self.led_verde = 12
        self.led_rojo = 7
        self.rgb_pins = {'R': 16, 'G': 21, 'B': 20}

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.led_verde, GPIO.OUT)
        GPIO.setup(self.led_rojo, GPIO.OUT)
        for pin in self.rgb_pins.values():
            GPIO.setup(pin, GPIO.OUT)

    def clear_leds(self):
        GPIO.output(self.led_verde, GPIO.LOW)
        GPIO.output(self.led_rojo, GPIO.LOW)
        for pin in self.rgb_pins.values():
            GPIO.output(pin, GPIO.LOW)

    def set_rgb_color(self, r, g, b):
        GPIO.output(self.rgb_pins['R'], GPIO.HIGH if r else GPIO.LOW)
        GPIO.output(self.rgb_pins['G'], GPIO.HIGH if g else GPIO.LOW)
        GPIO.output(self.rgb_pins['B'], GPIO.HIGH if b else GPIO.LOW)

    def blink_rgb(self, r, g, b, stop_event, duration=0.5):
        while not stop_event.is_set():
            self.set_rgb_color(r, g, b)
            time.sleep(duration)
            self.set_rgb_color(0, 0, 0)
            time.sleep(duration)

    def disco_mode(self, duration=5):
        start_time = time.time()
        GPIO.output(self.led_rojo, GPIO.LOW)
        GPIO.output(self.led_verde, GPIO.LOW)
        self.set_rgb_color(0, 0, 0)
        while time.time() - start_time < duration:
            GPIO.output(self.led_rojo, GPIO.HIGH)
            self.set_rgb_color(0, 0, 0)
            time.sleep(0.1)
            GPIO.output(self.led_verde, GPIO.HIGH)
            GPIO.output(self.led_rojo, GPIO.LOW)
            time.sleep(0.1)
            GPIO.output(self.led_verde, GPIO.LOW)
            self.set_rgb_color(0, 0, 1)
            time.sleep(0.1)

    def cleanup(self):
        self.clear_leds()
        GPIO.cleanup()
