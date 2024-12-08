from RPLCD.i2c import CharLCD
import time

class LCDHandler:
    def __init__(self):
        self.lcd = CharLCD('PCF8574', 0x27)

    def show_message_on_lcd(self, message):
        self.lcd.clear()
        lines = message.split('\n')
        for i, line in enumerate(lines[:2]):
            self.lcd.cursor_pos = (i, 0)
            self.lcd.write_string(line[:16])

    def show_temporary_message(self, message, duration):
        self.show_message_on_lcd(message)
        time.sleep(duration)
        self.lcd.clear()

    def clear(self):
        self.lcd.clear()
