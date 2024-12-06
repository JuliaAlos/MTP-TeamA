import time
import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD
import read_USB as USB
import os
from Short_range import master, slave, init_radio
from lcd_handler import LCDHandler
import threading
from multiprocessing import Process, Event, Queue

import LEDs_handler as leds



NAV_BUTTON_PIN = 23
SELECT_BUTTON_PIN = 24

GPIO.setmode(GPIO.BCM)
GPIO.setup(NAV_BUTTON_PIN, GPIO.IN)
GPIO.setup(SELECT_BUTTON_PIN, GPIO.IN)

#led_verde = 7 
#led_rojo = 12
#rgb_pins = {'R': 16, 'G': 20, 'B': 21}

#GPIO.setup(led_verde, GPIO.OUT)
GPIO.setup(led_rojo, GPIO.OUT)
#for pin in rgb_pins.values():
#    GPIO.setup(pin, GPIO.OUT)

button_pressed_flag = threading.Event()

lcd = LCDHandler()

#def clear_leds():
#    GPIO.output(led_verde, GPIO.LOW)
#    GPIO.output(led_rojo, GPIO.LOW)
#    for pin in rgb_pins.values():
#        GPIO.output(pin, GPIO.LOW)

#def set_rgb_color(r, g, b):
#    GPIO.output(rgb_pins['R'], GPIO.HIGH if r else GPIO.LOW)
#    GPIO.output(rgb_pins['G'], GPIO.HIGH if g else GPIO.LOW)
#    GPIO.output(rgb_pins['B'], GPIO.HIGH if b else GPIO.LOW)

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
    else:
        if menu == "Short":
            leds.set_rgb_color(1, 0, 0)  # RGB rojo
            if submenu == "Tx USB":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
            elif submenu == "Rx ST":
                GPIO.output(leds.led_verde, GPIO.HIGH)
            elif submenu == "Back":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
                GPIO.output(leds.led_verde, GPIO.HIGH)
        elif menu == "Mid":
            leds.set_rgb_color(0, 1, 0)  # RGB verde
            if submenu == "Tx USB":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
            elif submenu == "Rx ST":
                GPIO.output(leds.led_verde, GPIO.HIGH)
            elif submenu == "Back":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
                GPIO.output(leds.led_verde, GPIO.HIGH)
        elif menu == "Network":
            leds.set_rgb_color(0, 0, 1)  # RGB azul
            if submenu == "Tx USB":
                GPIO.output(leds.led_rojo, GPIO.HIGH)
            elif submenu == "Rx ST":
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
    leds.clear_leds()

    contents = USB.list_contents(path)
    selected_file = navigate_and_select_file(contents)

    if selected_file:
        full_path = os.path.join(path, selected_file)
        file_buffer = USB.read_file(full_path)
        # Cambia el LED RGB a azul
        leds.set_rgb_color(0, 0, 1)  # Azul

        # Espera a que el usuario presione el botón SELECT para iniciar la transmisión
        lcd.show_message_on_lcd("Press SELECT to\nStart Tx")
        while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW:
            time.sleep(0.1)
        # Apaga LED rojo y enciende LED verde
        GPIO.output(leds.led_rojo, GPIO.LOW)
        GPIO.output(leds.led_verde, GPIO.HIGH)

        master(file_buffer, lcd)

        # Transmisión finalizada
        leds.disco_mode()
        leds.clear_leds()

        
        
def slave_file(mode):
    # Apaga LEDs rojo y verde
    GPIO.output(leds.led_rojo, GPIO.LOW)
    GPIO.output(leds.led_verde, GPIO.LOW)
    # Enciende LED RGB azul
    leds.set_rgb_color(0, 0, 1)  # Azul

    slave(lcd)

    # Transmisión finalizada
    leds.disco_mode()
    leds.clear_leds()


def poweroff():
    clear_leds()
    lcd.show_message_on_lcd(f"     (-_-)\n     zzzzz")
    os.system("sudo poweroff")
    while True:
        pass

clear_leds()

# Aqui indicas que funcion quieres que llame
main_menu = MenuItem("Main Menu")
short_range = MenuItem("Short")
#short_range_tx = MenuItem("Tx USB", master_file)
#short_range_rx = MenuItem("Rx ST", slave_file)
short_range_tx = MenuItem("Tx USB", lambda: master_file('Short'))
short_range_rx = MenuItem("Rx ST", lambda: slave_file('Short'))

mid_range = MenuItem("Mid")
#mid_range_tx = MenuItem("Tx USB", master_file)
#mid_range_rx = MenuItem("Rx ST", slave_file)
mid_range_tx = MenuItem("Tx USB", lambda: master_file('Mid'))
mid_range_rx = MenuItem("Rx ST", lambda: slave_file('Mid'))

network_mode = MenuItem("Network")
#network_master = MenuItem("Tx USB") 
#network_slave = MenuItem("Rx ST")
network_master = MenuItem("Tx USB", lambda: master_file('Network'))
network_slave = MenuItem("Rx ST", lambda: slave_file('Network'))

poweroff= MenuItem("Power off",poweroff)


# Aqui sale cada opcion una vez entra a una de las opciones del menu principal

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
    GPIO.output(led_verde, GPIO.LOW)