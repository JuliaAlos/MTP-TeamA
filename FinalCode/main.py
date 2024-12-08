import time
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD
import read_USB as USB
import os
from Short_range import master, slave
from Medium_range import master_m, slave_m
from lcd_handler import LCDHandler
import threading
from multiprocessing import Process, Event, Queue

from LEDs_handler import LEDHandler

leds = LEDHandler()

NAV_BUTTON_PIN = 23
SELECT_BUTTON_PIN = 24

GPIO.setup(NAV_BUTTON_PIN, GPIO.IN)
GPIO.setup(SELECT_BUTTON_PIN, GPIO.IN)


button_pressed_flag = threading.Event()

lcd = LCDHandler()
current_index = 0

def update_leds(menu, submenu):
    print(f"Updating LEDs for Menu: {menu}, Submenu: {submenu}")
    leds.clear_leds()

    if menu == "Main Menu":
        if submenu == "Short":
            GPIO.output(leds.led_rojo, GPIO.HIGH)
        elif submenu == "Mid":
            GPIO.output(leds.led_verde, GPIO.HIGH)
        elif submenu == "Network":
            GPIO.output(leds.led_rojo, GPIO.HIGH)
            GPIO.output(leds.led_verde, GPIO.HIGH)
        elif submenu == "Save files USB":
            GPIO.output(leds.led_rojo, GPIO.HIGH)
            GPIO.output(leds.led_verde, GPIO.HIGH)
            leds.set_rgb_color(0, 0, 1)
    else:
        if menu == "Short":
            leds.set_rgb_color(1, 0, 0)  # RGB rojo
            if submenu == "Short: Tx":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
            elif submenu == "Short: Rx":
                GPIO.output(leds.led_verde, GPIO.HIGH)
            elif submenu == "Back":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
                GPIO.output(leds.led_verde, GPIO.HIGH)
        elif menu == "Mid":
            leds.set_rgb_color(0, 1, 0)  # RGB verde
            if submenu == "Mid: Tx":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
            elif submenu == "Mid: Rx":
                GPIO.output(leds.led_verde, GPIO.HIGH)
            elif submenu == "Back":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
                GPIO.output(leds.led_verde, GPIO.HIGH)
        elif menu == "Network":
            leds.set_rgb_color(0, 0, 1)  # RGB azul
            if submenu == "Net: Start Node":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
            elif submenu == "Net: Intermediate Node":
                GPIO.output(leds.led_verde, GPIO.HIGH)
            elif submenu == "Back":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
                GPIO.output(leds.led_verde, GPIO.HIGH)


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

def master_file(mode):
    lcd.show_message_on_lcd(f"Looking for USB")
    # Inicia parpadeo del LED RGB en el color del modo
    if mode == 'Short':
        blink_color = (1, 0, 0)  # Rojo
    elif mode == 'Mid':
        blink_color = (0, 1, 0)  # Verde
    elif mode == 'Network':
        blink_color = (0, 0, 1)  # Azul

    stop_blinking = threading.Event()
    blink_thread = threading.Thread(target=leds.blink_rgb, args=(*blink_color, stop_blinking))
    blink_thread.start()

    path = USB.get_file_usb_lcd()

    # Detiene el parpadeo
    stop_blinking.set()
    blink_thread.join()
    leds.set_rgb_color(0,1,1)

    contents = USB.list_contents(path)
    selected_file = navigate_and_select_file(contents)

    if selected_file:
        full_path = os.path.join(path, selected_file)
        file_buffer = USB.read_file(full_path)

        if mode == 'Short':
            leds.set_rgb_color(1,0,0)
            master(file_buffer, lcd)
        elif mode == 'Mid':
            leds.set_rgb_color(0,1,0)
            master_m(file_buffer, lcd)
        elif mode == 'Network':
            leds.set_rgb_color(0,0,1)

        leds.clear_leds()
    

def slave_file(mode):

    if mode == 'Short':
        slave(lcd)
        leds.set_rgb_color(1, 0, 0)
    elif mode == 'Mid':
        slave_m(lcd)
        leds.set_rgb_color(0, 1, 0)
    elif mode == 'Network':
        leds.set_rgb_color(0, 0, 1)

    # Transmisión finalizada
    leds.clear_leds()


def poweroff():
    clear_leds()
    lcd.show_message_on_lcd(f"     (-_-)\n     zzzzz")
    os.system("sudo poweroff")
    while True:
        pass

def save_files_USB():
    USB.save_file_USB("_MediumRange.txt")
    USB.save_file_USB("_ShortRange.txt")
    USB.save_file_USB("_Network.txt")
    USB.save_file_USB("network.log")

    current_menu = main_menu

leds.clear_leds()

main_menu = MenuItem("Main Menu")
short_range = MenuItem("Short")
short_range_tx = MenuItem("Short: Tx", lambda: master_file('Short'))
short_range_rx = MenuItem("Short: Rx", lambda: slave_file('Short'))

mid_range = MenuItem("Mid")
mid_range_tx = MenuItem("Mid: Tx", lambda: master_file('Mid'))
mid_range_rx = MenuItem("Mid: Rx", lambda: slave_file('Mid'))

network_mode = MenuItem("Network")
network_master = MenuItem("Net: Start Node", lambda: master_file('Network'))
network_slave = MenuItem("Net: Intermediate Node", lambda: slave_file('Network'))

poweroff= MenuItem("Power off",poweroff)

save_files = MenuItem("Save files USB",save_files_USB)

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
main_menu.add_submenu(save_files)

current_menu = main_menu


def show_current_menu():
    lcd.clear()
    lcd.show_message_on_lcd(f"{current_menu.name}:\n")
    lcd.cursor_pos = (1, 0)
    lcd.show_message_on_lcd(current_menu.submenus[current_index].name)
    update_leds(current_menu.name, current_menu.submenus[current_index].name)

try:
    show_current_menu()
    update_leds(current_menu.name, current_menu.submenus[current_index].name)
    while True:
        if GPIO.input(NAV_BUTTON_PIN) == GPIO.HIGH:
            current_index = (current_index + 1) % len(current_menu.submenus)
            show_current_menu()
            time.sleep(1)  

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
            time.sleep(1) 

except KeyboardInterrupt:
    pass

finally:
    lcd.clear()
    leds.clear_leds()
    leds.cleanup()
    GPIO.cleanup()
    GPIO.output(leds.led_verde, GPIO.LOW)