import time
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD
import read_USB as USB
import os 
from Short_range import master, slave, init_radio
from lcd_handler import LCDHandler

NAV_BUTTON_PIN = 23  
SELECT_BUTTON_PIN = 24  

GPIO.setmode(GPIO.BCM)
GPIO.setup(NAV_BUTTON_PIN, GPIO.IN)
GPIO.setup(SELECT_BUTTON_PIN, GPIO.IN)

lcd = LCDHandler()

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

def navigate_and_select_file(contents):
    if not contents:
        lcd.show_temporary_message("No files found.", 2)
        return None

    current_index = 0
    lcd.show_message_on_lcd(f"Select File:\n{contents[current_index][:16]}")
    while True:
        time.sleep(0.3)
        if GPIO.input(NAV_BUTTON_PIN) == GPIO.HIGH:
            current_index = (current_index + 1) % len(contents)
            lcd.show_message_on_lcd(f"Select File:\n{contents[current_index][:16]}")
            time.sleep(0.3)

        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.HIGH:
            selected_file = contents[current_index]
            lcd.show_temporary_message(f"Selected:\n{selected_file[:16]}", 2)
            return selected_file

def master_file():
    path = USB.get_file_usb_lcd()
    contents = USB.list_contents(path)
    selected_file = navigate_and_select_file(contents)
    print(f"esto es el selected file{selected_file}")

    if selected_file:
        full_path = os.path.join(path, selected_file)
        file_buffer = USB.read_file(full_path)
        master(file_buffer, lcd)
    return None

def slave_file():
    slave(lcd)

def poweroff():
    os.system("sudo poweroff now")

main_menu = MenuItem("Main Menu")
short_range = MenuItem("Short")
short_range_tx = MenuItem("Tx USB", master_file)
short_range_rx = MenuItem("Rx ST", slave_file)
mid_range = MenuItem("Mid")
mid_range_tx = MenuItem("Tx USB")
mid_range_rx = MenuItem("Rx ST")
network_mode = MenuItem("Network")
network_master = MenuItem("Master") 
network_slave = MenuItem("Slave ST")
poweroff= MenuItem("Power off", poweroff)

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
main_menu.add_submenu(poweroff)

current_menu = main_menu
current_index = 0

def show_current_menu():
    lcd.clear()
    lcd.show_message_on_lcd(f"{current_menu.name}:\n")
    lcd.cursor_pos = (1, 0)
    lcd.show_message_on_lcd(current_menu.submenus[current_index].name)

try:
    show_current_menu()
    while True:
        if GPIO.input(NAV_BUTTON_PIN) == GPIO.HIGH:
            current_index = (current_index + 1) % len(current_menu.submenus)
            show_current_menu()
            time.sleep(0.3)  

        if GPIO.input(SELECT_BUTTON_PIN) == GPIO.HIGH:
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
