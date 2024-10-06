from pyrf24 import RF24, RF24_PA_LOW, RF24_DRIVER
import os
import struct
from bitarray import bitarray
import time

CSN_PIN = 0 # The pin attached to Chip Select in RF module
CE_PIN = 13 # The pin attached to Chip Enable in RF module

radio = RF24(CE_PIN, CSN_PIN)

if not radio.begin():
    raise RuntimeError("Unable to initialize radio")


address = "011" # radio address

############## CONFIG PARAMETERS ##################
radio.setChannel()
radio.setPayloadSize()
radio.setPAlevel() #Desired power amplifier level (int 0-3) -> (-18, -12, -6, 0)dBm
radio.setDataRate() #Specify data rate (int 0-2) -> (1Mbps, 2Mbps, 250kbps)
radio.setCRCLength() #Specify CRC length (int 0-2) -> (disable, 8bit, 16bit)
radio.setAutoACK()
chunk_size = 32 #Amount of data to put into a single packet in bytes
####################################################

radio.openReadingPipe(1, address)
payload =[0.0]


def slave(timeout=6):
    """
    Listens for incoming data on the radio and saves it to a file.

    This function puts the radio into RX mode and listens for incoming data
    for a specified timeout period. If data is received, it is appended to a
    bytearray. The timeout timer is reset each time data is received. Once the
    timeout period has elapsed, the received data is written to a file named
    'received_prueba.txt' in the same directory as this script.

    Args:
        timeout (int, optional): The time in seconds to listen for incoming data. Defaults to 6.

    Returns:
        None
    """
    radio.startListening()  # put radio in RX mode
    data = bytearray()
    start_timer = time.monotonic()
    while (time.monotonic() - start_timer) < timeout:
        has_payload, pipe_number = radio.available_pipe()
        if has_payload:
            # fetch 1 payload from RX FIFO
            buffer = radio.read(radio.payloadSize)
            data.extend(buffer)
            start_timer = time.monotonic()  # reset the timeout timer

    file_path = os.path.join(os.path.dirname(__file__), 'received_prueba.txt')
    with open(file_path, 'wb') as file:
        file.write(data)
    print(f"Data received and saved to {file_path}")

if __name__ == "__main__":
    try:
        slave()
    except KeyboardInterrupt:
        print("Ending reception, interrupt detected")
        radio.powerDown()


