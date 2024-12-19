import sys
sys.path.append('/usr/local/lib/python3.11/dist-packages/RF24-1.4.10-py3.11-linux-aarch64.egg')
import time
import math
from RF24 import RF24, RF24_PA_LOW, RF24_PA_HIGH, RF24_PA_MAX, RF24_1MBPS, RF24_2MBPS, RF24_250KBPS, RF24_DRIVER
import struct
import json
import logging
import subprocess
from typing import List
import os
import shutil
from datetime import datetime
import hashlib
import RPi.GPIO as GPIO
import threading
from time import sleep
import random
from LEDs_handler import LEDHandler
import read_USB as USB

leds = LEDHandler()

# logging.debug('This is a debug message')
# logging.info('This is an info message')
# logging.warning('This is a warning message')
# logging.error('This is an error message')
# logging.critical('This is a critical message')

###### NETWORK MODE PARAMETERS  ######
RTS = 0b1111
CTS = 0b1010
FR = 0b0000

ACK = 0b11111111
NACK = 0b00000000

# Addressing
A1 = 0b1000
A2 = 0b1001
C1 = 0b0010
C2 = 0b0011
D1 = 0b0100
D2 = 0b0101
BROADCAST = 0b1111

# Channels
channel_num = {
    A1: 96,
    A2: 91,
    C1: 92,
    C2: 93,
    D1: 94,
    D2: 95,
    BROADCAST: 99,
}

channel_bin = {
    A1: 0b1000,
    A2: 0b1001,
    C1: 0b0010,
    C2: 0b0011,
    D1: 0b0100,
    D2: 0b0101,
}

NUMBER_RETRY = 20

# Backoffs
FR_BACKOFF = 60
RTS_BACKOFF = 45
BLACKLIST_TIMEOUT = 100

# Listen channel time [ms]
FR_LISTEN_BEFORE = 100
RTS_LISTEN_BEFORE = 10

# Timeouts wait response [ms]
RTS_TIMEOUT = 1000
FR_TIMEOUT = 1000
FILE_TIMEOUT = 1000

# Other parametersFILE_TIMEOUT
MAX_SIZE = 32
HEADER_SIZE = 1
PAYLOAD_SIZE = MAX_SIZE - HEADER_SIZE
CTS_SIZE = 2
RTS_SIZE = 2
RF_SIZE = 1

#######################################
BLACKLIST = []
FILE_BUFF = None
PACKETS = []

LOCAL_ADDRESS = None
LOCAL_CHANNEL = None

radio = None
led_green = None
led_red = None
led_file = None
button_start = None
button_stop = None
finish_transmission = False

def print_as_bits(buffer):
    try:
        bits = ''.join(format(byte, '08b') for byte in buffer)
        return ' '.join(bits)
    except:
        return ""

def button_monitor():
    global button_stop
    print(f"Button stop {button_stop}")
    while True:
        if GPIO.input(button_stop) == GPIO.HIGH:
            press_start_time = time.time()

            while GPIO.input(button_stop) == GPIO.HIGH:
                if time.time() - press_start_time >= 1:
                    print("Button pressed")
                    logging.warning('Timeout, transmission finish')
                    global finish_transmission
                    finish_transmission = True
                    global led_red
                    global led_green
                    GPIO.output(led_green, GPIO.LOW)
                    GPIO.output(led_red, GPIO.HIGH)
                    break

        time.sleep(0.5)

#################################################

def navigate_and_select_file(contents, lcd):
    global button_start
    global button_stop

    if not contents:
        lcd.show_temporary_message("No files found.", 2)
        return None

    current_index = 0
    lcd.show_message_on_lcd(f"Select File:\n{contents[current_index][:16]}")
    while True:
        time.sleep(0.3)
        if GPIO.input(button_stop) == GPIO.HIGH:
            current_index = (current_index + 1) % len(contents)
            lcd.show_message_on_lcd(f"Select File:\n{contents[current_index][:16]}")
            time.sleep(0.3)

        if GPIO.input(button_start) == GPIO.HIGH:
            selected_file = contents[current_index]
            lcd.show_temporary_message(f"Selected:\n{selected_file[:16]}", 2)
            return selected_file

def initialize_transciever(has_file, lcd):
    global FILE_BUFF
    global md5
    global PACKETS
    global button_start
    global finish_transmission

    file_log = 'network.log'
    if os.path.exists(file_log):
        os.remove(file_log)

    logging.basicConfig(
        filename=file_log,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    logging.debug('Set up device config')
    set_up_config()

    global led_file
    global led_red
    global led_green


    if has_file:
        stop_blinking = threading.Event()
        blink_thread = threading.Thread(target=leds.blink_rgb, args=(*(0,0,1), stop_blinking))
        blink_thread.start()
        path = USB.get_file_usb_lcd()
        # Detiene el parpadeo
        stop_blinking.set()
        blink_thread.join()
        leds.set_rgb_color(0,1,1)

        contents = USB.list_contents(path)
        selected_file = navigate_and_select_file(contents,lcd)

        if selected_file:
            full_path = os.path.join(path, selected_file)
            FILE_BUFF = USB.read_file(full_path)
            print("Reading file")
            logging.info('File load %s', full_path)
            md5 = get_md5_hash(FILE_BUFF)
            logging.info('File readed, hash %s', md5)
            PACKETS = build_packets(FILE_BUFF, md5)
        lcd.show_message_on_lcd(f"Initial Node\nReady to start")
    else:
        lcd.show_message_on_lcd(f"Intermediate Node\nReady to start")

    monitor_thread = threading.Thread(target=button_monitor)
    monitor_thread.daemon = True  # Allow thread to exit when main program exits
    monitor_thread.start()

    GPIO.output(led_file, GPIO.HIGH)
    GPIO.output(led_green, GPIO.LOW)
    GPIO.output(led_red, GPIO.HIGH)
    while True:
        time.sleep(0.3)
        if GPIO.input(button_start) == GPIO.HIGH:
            finish_transmission = False
            print("Network mode started")
            logging.info('Network mode started')
            GPIO.output(led_green, GPIO.HIGH)
            GPIO.output(led_red, GPIO.LOW)
            break

    lcd.show_message_on_lcd(f"Discovery channel")
    if has_file:
        listenBroadcast(lcd)
    else:
        GPIO.output(led_red, GPIO.LOW)
        request_file(lcd)

    lcd.show_message_on_lcd(f"Finish Network\n     (^_^)")
    leds.disco_mode()
    global radio

    radio.stopListening()
    radio.powerDown()
    file_path = 'MTP-F24-NM-A-RX.txt'
    print(f"{FILE_BUFF}")
    if len(FILE_BUFF) >0:
        with open(file_path, 'wb') as file:
            file.write(FILE_BUFF)
    leds.clear_leds()
    lcd.show_message_on_lcd("Looking for USB driver")
    save_file = USB.save_file_USB(file_path)
    lcd.show_message_on_lcd(f"File saved to \n{save_file}")
    time.sleep(1)

    save_file = USB.save_file_USB('network.log')
    lcd.show_message_on_lcd(f"File saved to \n{save_file}")
    time.sleep(5)
    lcd.show_message_on_lcd(f"     (O_O)")
    time.sleep(10)

def set_up_config():
    global LOCAL_ADDRESS
    global LOCAL_CHANNEL
    global radio
    global button_start
    global button_stop
    global led_green
    global led_red
    global led_file

    with open("config.json", 'r') as file:
        config = json.load(file)

        match config['transciever_id']:
            case "A1":
                LOCAL_ADDRESS = A1
                LOCAL_CHANNEL = channel_bin[A1]
            case "A2":
                LOCAL_ADDRESS = A2
                LOCAL_CHANNEL = channel_bin[A2]
            case "C1":
                LOCAL_ADDRESS = C1
                LOCAL_CHANNEL = channel_bin[C1]
            case "C2":
                LOCAL_ADDRESS = C2
                LOCAL_CHANNEL = channel_bin[C2]
            case "D1":
                LOCAL_ADDRESS = D1
                LOCAL_CHANNEL = channel_bin[D1]
            case "D2":
                LOCAL_ADDRESS = D2
                LOCAL_CHANNEL = channel_bin[D2]
            case _:
                print("transciever_id wrong id")
                logging.critical('transciever_id wrong id')

        led_green = config['led']['green']
        led_red = config['led']['red']
        led_file = config['led']['file']
        button_start = config['button']['start']
        button_stop = config['button']['stop']
        CE_PIN = config['radio']['ce_pin']
        CSN_PIN = config['radio']['cns_pin']

        GPIO.setmode(GPIO.BCM)
        GPIO.setup(button_start, GPIO.IN)
        GPIO.setup(button_stop, GPIO.IN)
        GPIO.setup(led_green, GPIO.OUT)
        GPIO.setup(led_red, GPIO.OUT)
        GPIO.setup(led_file, GPIO.OUT)
        GPIO.output(led_green, GPIO.LOW)
        GPIO.output(led_file, GPIO.LOW)
        GPIO.output(led_red, GPIO.HIGH)

        match config['radio']['pa_level']:
            case "RF24_PA_LOW":
                PA_LEVEL = RF24_PA_LOW
            case "RF24_PA_HIGH":
                PA_LEVEL = RF24_PA_HIGH
            case "RF24_PA_MAX":
                PA_LEVEL = RF24_PA_MAX
            case _:
                print("PA wrong config value")
                logging.critical('PA wrong config value')

        match config['radio']['data_rate']:
            case "RF24_1MBPS":
                DATA_RATE = RF24_1MBPS
            case "RF24_2MBPS":
                DATA_RATE = RF24_2MBPS
            case "RF24_250KBPS":
                DATA_RATE = RF24_250KBPS
            case _:
                print("Data rate wrong config value")
                logging.critical('Data rate wrong config value')

        print(f"LEDs: Green {led_green}, Red {led_red}")
        print(f"Buttons: Start {button_start}, Stop {button_stop}")

        radio = RF24(CE_PIN, CSN_PIN)

        # initialize the nRF24L01 on the spi bus
        if not radio.begin():
            raise RuntimeError("radio hardware is not responding")

        radio.setPALevel(PA_LEVEL)
        radio.setDataRate(DATA_RATE)
        radio.setAutoAck(False)
        radio.setAddressWidth(3)
        radio.enableDynamicPayloads()

        radio.openWritingPipe(BROADCAST)
        radio.openReadingPipe(1, BROADCAST)
        radio.setChannel(channel_num[BROADCAST])

        logging.info('Device %s waiting to start', config['transciever_id'])

def channel_busy(waiting_time):
    # TODO: Implement listen to channel

    random_time = random.randint(1, waiting_time)

    logging.debug('Start listen channel time: %s', random_time)
    timeout = time.monotonic() * 1000 + random_time
    while time.monotonic() * 1000 < timeout and not finish_transmission:
        pass
    logging.debug('Channel free to transmit')

def check_blacklist(device):
    global BLACKLIST

    current_time = time.monotonic() * 1000
    [(node, time) for node, time in BLACKLIST if time > current_time]

    for node in BLACKLIST:
        if node[0] == device:
            logging.warning('Device found in BLACKLIST: %s', device)
            return True
    return False

def add_blacklist(device):
    global BLACKLIST
    logging.warning('Device added in BLACKLIST: %s', device)
    finish_time = time.monotonic() * 1000 + BLACKLIST_TIMEOUT
    BLACKLIST.append((device, finish_time))

def get_channel_value(channel_bin_key):
    if channel_bin_key in channel_bin:
        return channel_num.get(channel_bin_key, None)
    else:
        return None

def request_file(lcd):
    global radio
    global finish_transmission

    FR_buffer = struct.pack('B', ((FR << 4) & 0xF0) | (LOCAL_ADDRESS & 0x0F))
    print("FR packet:", print_as_bits(FR_buffer))

    found_node = None
    has_file = False

    while not has_file and not finish_transmission:
        channel_busy(FR_LISTEN_BEFORE + FR_BACKOFF)
        radio.flush_rx()

        print("SEND RF")
        logging.info('SEND RF %s', print_as_bits(FR_buffer))
        radio.stopListening()
        radio.flush_tx()
        radio.write(FR_buffer)
        radio.startListening()

        logging.info('Waiting response...')
        timeout = time.monotonic() * 1000 + FR_TIMEOUT
        while time.monotonic() * 1000 < timeout and not finish_transmission:
            if radio.available():
                has_payload, pipe_number = radio.available_pipe()
                # grab the incoming payload
                if has_payload:
                    payload_size = radio.getDynamicPayloadSize()
                    response_buffer = radio.read(payload_size)
                    print("RTS?", print_as_bits(response_buffer))
                    logging.debug('Received packet: %s', print_as_bits(response_buffer))

                    if payload_size >= RTS_SIZE:
                        packet_id = (response_buffer[0] & 0xF0) >> 4
                        req_address = (response_buffer[1] & 0xF0) >> 4
                        if packet_id == RTS and req_address == LOCAL_ADDRESS:
                            print(f"REVEC RTS")
                            res_address = response_buffer[0] & 0x0F
                            proposed_channel = response_buffer[1] & 0x0F
                            logging.info('Received RTS from %s', print_as_bits(bytes(res_address)))
                            if not check_blacklist(res_address):
                                found_node = (res_address,proposed_channel)
                                break
                        else: # Discard packet, no for this device
                            pass

        if found_node != None and not finish_transmission:
            res_address, channel = found_node

            CTS_buffer = struct.pack('BB', ((CTS << 4) & 0xF0) | (res_address & 0x0F), (((LOCAL_ADDRESS << 4) & 0xF0) | (channel & 0x0F)))
            logging.info('CTS packet %s', print_as_bits(CTS_buffer))
            print('CTS packet ', print_as_bits(CTS_buffer))

            logging.info('Send CTS')
            print('Send CTS')
            radio.stopListening()
            radio.flush_tx()
            radio.write(CTS_buffer)
            radio.startListening()

            channel = get_channel_value(proposed_channel)
            logging.info('Switch to dedicated channel %s', channel)
            has_file = receive_file(LOCAL_ADDRESS, res_address, channel,lcd)

    if not finish_transmission:
        lcd.show_message_on_lcd(f"File received\n     (^_^)")
        listenBroadcast(lcd)

def listenBroadcast(lcd):
    global radio
    global finish_transmission

    radio.printPrettyDetails()
    radio.startListening()
    radio.flush_rx()
    radio.printPrettyDetails()
    logging.debug('Listening Discovery channel...')
    print("Listening Discovery channel...")
    while not finish_transmission:
        if radio.available():
            payload_size = radio.getDynamicPayloadSize()
            response_buffer = radio.read(payload_size)
            logging.debug('Message recieved: %s',print_as_bits(response_buffer))
            print(f"Message recieved: {print_as_bits(response_buffer)}")

            if payload_size >= RF_SIZE:
                packet_id = (response_buffer[0] & 0xF0) >> 4
                req_address = response_buffer[0] & 0x0F

                # Check if the packet is a request for the file
                if packet_id == FR:
                    print(f"FR from {req_address}")
                    logging.info('FR received')
                    requestToSend(req_address,lcd)
                    radio.flush_rx()
                    radio.startListening()
                    logging.debug('Listening Discovery channel...')
                    print("Listening Discovery channel...")

def requestToSend(req_address,lcd):
    global radio
    global finish_transmission

    RTS_buffer = struct.pack('BB', ((RTS<<4) & 0xF0) | (LOCAL_ADDRESS & 0x0F), ((req_address<<4) & 0xF0) | (LOCAL_CHANNEL & 0x0F))
    node_info = None

    logging.info('RTS packet %s', print_as_bits(RTS_buffer))
    print(f"RTS packet {print_as_bits(RTS_buffer)}")

    channel_busy(RTS_LISTEN_BEFORE + RTS_BACKOFF)

    logging.info('Send RTS')
    # SEND RTS
    radio.stopListening()
    radio.flush_tx()
    radio.write(RTS_buffer)
    radio.startListening()
    radio.flush_rx()

    print("Send RTS")

    # WAIT RESPONSE CTS
    timeout = time.monotonic() * 1000 + RTS_TIMEOUT
    while time.monotonic() * 1000 < timeout and not finish_transmission:
        if radio.available():
            has_payload, pipe_number = radio.available_pipe()
            # grab the incoming payload
            if has_payload:
                payload_size = radio.getDynamicPayloadSize()
                response_buffer = radio.read(payload_size)
                logging.debug('Message recieved: %s', print_as_bits(response_buffer))

                if payload_size >= CTS_SIZE:
                    packet_id = (response_buffer[0] & 0xF0) >> 4
                    res_address = response_buffer[0] & 0x0F
                    if packet_id == CTS and res_address == LOCAL_ADDRESS:
                        print("Recieved CTS")
                        logging.debug('CTS recieved')

                        req_address = (response_buffer[1] & 0xF0) >> 4
                        channel = response_buffer[1] & 0x0F
                        node_info = (req_address,channel)
                        break
                    else: # Discard packet, no for this device
                        pass

    radio.stopListening()  # put radio in TX mode

    if node_info != None and not finish_transmission:
        req_address, proposed_channel = node_info
        channel = get_channel_value(proposed_channel)
        logging.info('Switch to dedicated channel %s', channel)
        print(f"Switch to dedicated channel {channel}")
        send_file(LOCAL_ADDRESS, req_address, channel,lcd)
    elif not finish_transmission:
        print("No node has replay the RTS")
        logging.warning('Node has not replay the RTS')

def get_md5_hash(buff):
    hash_func = hashlib.md5()
    hash_func.update(buff)
    return hash_func.digest()

def build_packets(file_buff: bytes, md5) -> List[bytes]: # La forma de definir esta funcion detecta que sois unos copiones
    packet_buff = []
    length = len(file_buff)
    num_packets = math.ceil(length / PAYLOAD_SIZE) 
    num_packets = max(0, min(254, num_packets))

    packet_buff.append(struct.pack('BB16s', 0, num_packets + 1, md5))

    for i in range(0, num_packets):
        header = struct.pack('B', i + 1)
        payload = file_buff[i * PAYLOAD_SIZE:PAYLOAD_SIZE * (i + 1)]
        packet_buff.append(header + payload)

    for i in range(0,len(packet_buff)):
        print(f"{packet_buff[i]}")

    return packet_buff

def reconfigure_radio(local_address, remote_address, channel, lcd):
    global radio
    radio.setAutoAck(True)
    radio.enableAckPayload()
    radio.openWritingPipe(local_address)
    radio.openReadingPipe(1, remote_address)
    radio.setChannel(channel)
    radio.flush_rx()
    radio.flush_tx()
    lcd.show_message_on_lcd(f"Dedicate channel {channel}")

def close_dedicated_channel(lcd):
    global radio
    radio.setAutoAck(False)
    radio.openWritingPipe(BROADCAST)
    radio.openReadingPipe(1, BROADCAST)
    radio.setChannel(channel_num[BROADCAST])
    radio.flush_rx()
    radio.flush_tx()
    radio.stopListening()
    lcd.show_message_on_lcd(f"Discovery channel")

def send_file(local_address, remote_address, channel, lcd):
    global PACKETS
    global finish_transmission

    print("Sending file....")
    logging.info('*************************************')
    logging.info('Sending file...')
    print(f"My {local_address}, dest {remote_address}, channel {channel}")
    logging.info('My %s, dest %s, channel %s', local_address, remote_address, channel)
    logging.info('*************************************')

    reconfigure_radio(local_address, remote_address, channel,lcd)
    radio.stopListening()  # put radio in TX mode
    radio.flush_tx()
    timeout = time.monotonic() * 1000 + FILE_TIMEOUT/10
    while time.monotonic() * 1000 < timeout:
        pass

    i = 0
    while i < len(PACKETS) and not finish_transmission:
        logging.debug('Send packet %s', i)
        print(f"Send packet {i}")
        for m in range(NUMBER_RETRY):
            radio.write(PACKETS[i])
            
            has_payload, pipe_number = radio.available_pipe()
            if has_payload:
                length = radio.getDynamicPayloadSize()
                ack = radio.read(length)
                if length >= 1 and ack[0] == i:
                    print(f"Packet {i} received")
                    logging.debug('Packet %s received', i)
                    i += 1
                    break
            if finish_transmission:
                break
        else:
            logging.error('Maximum number retransmission link broked')
            print("Maximum number retransmission link broked")
            break

    logging.info('Transmission end')
    print("Transmission end")
    logging.info('*************************************')

    close_dedicated_channel(lcd)
    # Return to broadcast channel

def receive_file(local_address, remote_address, channel, lcd):
    global PACKETS
    global FILE_BUFF
    global finish_transmission

    PACKETS = []

    print("Receiving file....")
    print(f"My {local_address}, dest {remote_address}, channel {channel}")
    logging.info('*************************************')
    logging.info('Receiving file...')
    logging.info('My %s, dest %s, channel %s', local_address, remote_address, channel)
    logging.info('*************************************')

    reconfigure_radio(local_address, remote_address, channel,lcd)

    radio.startListening()
    receive_payload = b''
    next_packet = 0
    num_packets = None
    md5 = None
    radio.writeAckPayload(1, struct.pack('B', next_packet))

    timeout = time.monotonic() * 1000 + FILE_TIMEOUT
    while time.monotonic() * 1000 < timeout and not finish_transmission:
        has_payload, pipe_number = radio.available_pipe()
        try:
            if has_payload:
                length = radio.getDynamicPayloadSize()
                new_payload = radio.read(length)
                print(f"{new_payload}")
                if next_packet == 0:
                    radio.writeAckPayload(1, struct.pack('B', next_packet+1))

                    num, num_packets, md5 = struct.unpack('BB16s', new_payload)
                    PACKETS.append(new_payload)
                    print(f"CONTROL PACKET RECEIVED, total packets {num_packets}, hash {md5}")
                    logging.debug('CONTROL PACKET RECEIVED, total packets %s, hash %s', num_packets, md5)
                    timeout = time.monotonic() * 1000 + FILE_TIMEOUT
                    next_packet += 1

                elif next_packet == new_payload[0]:
                    radio.writeAckPayload(1, struct.pack('B', next_packet+1))
                    PACKETS.append(new_payload)
                    receive_payload += new_payload[HEADER_SIZE:MAX_SIZE]
                    print(f"PACKET RECEIVED: {next_packet}")
                    logging.debug('PACKET RECEIVED: %s', next_packet)
                    next_packet += 1
                    timeout = time.monotonic() * 1000 + FILE_TIMEOUT
                radio.writeAckPayload(1, struct.pack('B', new_payload[0]))

                if next_packet == num_packets:
                    break
        except:
            print("Wrong size")

    md5_file = get_md5_hash(receive_payload)
    if md5_file == md5:
        FILE_BUFF = receive_payload
        print("File received successfully")
        logging.info('File received successfully')
        logging.info('*************************************')
        global led_file
        GPIO.output(led_file, GPIO.HIGH)
        print(f"{FILE_BUFF}")
        with open("MTP-F24-NM-A-RX.txt", 'wb') as file:
            file.write(FILE_BUFF)
        print(f"{FILE_BUFF}")

    else:
        add_blacklist(remote_address)
        print("Failed receiving file")
        print(f"Hash {md5_file}, expected {md5}")
        logging.critical('Failed receiving file')
        logging.critical('Hash %s, expected %s', md5_file, md5)
        logging.info('*************************************')

    close_dedicated_channel(lcd)
    return (md5_file == md5)

if __name__ == "__main__":
    user_input = input("Node type? Has file '0' or Not has file '1' -> ")
    has_file = user_input == '1'

    try:
        initialize_transciever(has_file)

    except KeyboardInterrupt:
        print("\nProgram interrupted. Exiting gracefully...")
        radio.powerDown()
