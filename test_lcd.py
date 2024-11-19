import time
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD
import read_USB as USB
import os

NAV_BUTTON_PIN = 23  
SELECT_BUTTON_PIN = 24  

GPIO.setmode(GPIO.BCM)
GPIO.setup(NAV_BUTTON_PIN, GPIO.IN)
GPIO.setup(SELECT_BUTTON_PIN, GPIO.IN)

lcd = CharLCD('PCF8574', 0x27)

class MenuItem:
    def __init__(self, name, action=None, parent=None):
        self.name = name
        self.action = action  
        self.submenus = []
        self.parent = parent

    def add_submenu(self, submenu):
        submenu.parent = self
        self.submenus.append(submenu)

    def execute(self):
        if callable(self.action):  
            self.action()
        elif self.action:  
            lcd.clear()
            lcd.write_string(f"Executing {self.name}")
            time.sleep(2)
            lcd.clear()


def navigate_and_select(contents):
    """Navigate through the list and allow the user to select an item."""
    if not contents:
        lcd.clear()
        lcd.write_string("No files found.")
        time.sleep(2)
        lcd.clear()
        return None

    current_index = 0
    lcd.clear()
    lcd.write_string("Select File:\n")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(contents[current_index][:16])  # Limit display to 16 chars
    while True:
        time.sleep(0.3)
        if GPIO.input(NAV_BUTTON_PIN) == GPIO.HIGH:
            current_index = (current_index + 1) % len(contents)  # Cycle through list
            lcd.clear()
            lcd.write_string("Select File:\n")
            lcd.cursor_pos = (1, 0)
            lcd.write_string(contents[current_index][:16])  # Limit display to 16 chars
            time.sleep(0.3)

        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.HIGH:
            selected_file = contents[current_index]
            lcd.clear()
            lcd.write_string("Selected:\n")
            lcd.cursor_pos = (1, 0)
            lcd.write_string(selected_file[:16])  # Display the selected file
            time.sleep(3)
            lcd.clear()
            return selected_file

def master():
    """Master function to list and select a file from USB."""
    path = USB.get_file_usb_lcd()
    print(f"esto es el path {path}")
    contents = USB.list_contents(path)
    selected_file = navigate_and_select(contents)

    if selected_file:
        full_path = os.path.join(path, selected_file)
        print(f"File selected: {full_path}")
        return full_path
    return None

def slave():
    lcd.clear()
    lcd.write_string("Exec Slave")
    time.sleep(2)
    lcd.clear()

main_menu = MenuItem("Main Menu")

short_range = MenuItem("Short")
short_range_tx = MenuItem("Tx USB", master)
short_range_rx = MenuItem("Rx ST", slave)

mid_range = MenuItem("Mid")
mid_range_tx = MenuItem("Tx USB", master)
mid_range_rx = MenuItem("Rx ST", slave)

network_mode = MenuItem("Network", master)
network_master = MenuItem("Master", slave) 
network_slave = MenuItem("Slave ST")

power_off = MenuItem("Power off")

short_range.add_submenu(short_range_tx)
short_range.add_submenu(short_range_rx)
short_range.add_submenu(MenuItem("Back"))

mid_range.add_submenu(mid_range_tx)
mid_range.add_submenu(mid_range_rx)
mid_range.add_submenu(MenuItem("Back"))

network_mode.add_submenu(network_master)
network_mode.add_submenu(network_slave)
network_mode.add_submenu(MenuItem("Back"))

main_menu.add_submenu(short_range)
main_menu.add_submenu(mid_range)
main_menu.add_submenu(network_mode)
main_menu.add_submenu(power_off)

current_menu = main_menu
current_index = 0

def show_current_menu():
    lcd.clear()
    lcd.write_string(f"{current_menu.name}:\n")
    lcd.cursor_pos = (1, 0)
    lcd.write_string(current_menu.submenus[current_index].name)

try:
    show_current_menu()
    while True:
        if GPIO.input(NAV_BUTTON_PIN) == GPIO.HIGH:
            if GPIO.input(NAV_BUTTON_PIN) == GPIO.LOW:
                current_index = (current_index + 1) % len(current_menu.submenus)
                show_current_menu()
                time.sleep(0.3)  

        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.HIGH:
            if GPIO.input(NAV_BUTTON_PIN) == GPIO.LOW:
                selected_item = current_menu.submenus[current_index]
                if selected_item.name == "Back":
                    if current_menu.parent:
                        current_menu = current_menu.parent
                        current_index = 0
                elif selected_item.submenus:
                    current_menu = selected_item
                    current_index = 0
                else:

                    selected_item.execute()

            show_current_menu()
            time.sleep(0.3) 

except KeyboardInterrupt:
    pass

finally:
    lcd.clear()
    GPIO.cleanup()
