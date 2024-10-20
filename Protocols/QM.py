"""
A simple example of streaming data from 1 nRF24L01 transceiver to another.

This example was written to be used on 2 devices acting as 'nodes'.

See documentation at https://nRF24.github.io/RF24
"""

import time
import math
from RF24 import RF24, RF24_PA_LOW, RF24_DRIVER
import struct

print(__file__)  # print example name

########### USER CONFIGURATION ###########
# CE Pin uses GPIO number with RPi and SPIDEV drivers, other drivers use
# their own pin numbering
# CS Pin corresponds the SPI bus number at /dev/spidev<a>.<b>
# ie: radio = RF24(<ce_pin>, <a>*10+<b>)
# where CS pin for /dev/spidev1.0 is 10, /dev/spidev1.1 is 11 etc...
CSN_PIN = 0  # GPIO8 aka CE0 on SPI bus 0: /dev/spidev0.0
EOT = b'EOT' + b'\x00' * (32 - len(b'EOT'))   # end of transmission

if RF24_DRIVER == "MRAA":
    CE_PIN = 15  # for GPIO22
elif RF24_DRIVER == "wiringPi":
    CE_PIN = 3  # for GPIO22
else:
    CE_PIN = 22
    
radio = RF24(CE_PIN, CSN_PIN)

# initialize the nRF24L01 on the spi bus
if not radio.begin():
    raise RuntimeError("radio hardware is not responding")

# For this example, we will use different addresses
# An address need to be a buffer protocol object (bytearray)
address = [b"1Node", b"2Node"]
# It is very helpful to think of an address as a path instead of as
# an identifying device destination

# to use different addresses on a pair of radios, we need a variable to
# uniquely identify which address this radio will use to transmit
# 0 uses address[0] to transmit, 1 uses address[1] to transmit
radio_number = bool(
    int(input("Which radio is this? Enter '0' or '1'. Defaults to '0' ") or 0)
)

# set the Power Amplifier level to -12 dBm since this test example is
# usually run with nRF24L01 transceivers in close proximity of each other
radio.setPALevel(RF24_PA_LOW)  # RF24_PA_MAX is default

# set the TX address of the RX node into the TX pipe
radio.openWritingPipe(address[radio_number])  # always uses pipe 0

# set the RX address of the TX node into a RX pipe
radio.openReadingPipe(1, address[not radio_number])  # using pipe 1


# Specify the number of bytes in the payload. This is also used to
# specify the number of payloads in 1 stream of data
SIZE = 30  # this is the default maximum payload size

# To save time during transmission, we'll set the payload size to be only
# what we need. For this example, we'll be using the default maximum 32
radio.payloadSize = SIZE

# for debugging, we have 2 options that print a large block of details
# (smaller) function that prints raw register values
# radio.printDetails()
# (larger) function that prints human readable data
radio.printPrettyDetails()


def read_file() -> bytes:
    """Returns a dynamically created payloads

    :param int buf_iter: The position of the payload in the data stream
    """
    # we'll use `SIZE` for the number of payloads in the list and the
    # payloads' length
    # prefix payload with a sequential letter to indicate which
    # payloads were lost (if any)
    # Specify the path to the file
    file_path = 'testfile.txt'
    # Open the file for reading in binary mode
    try:
        # Open the file for reading in binary mode
        with open(file_path, 'rb') as file:
            # Read the contents of the file as bytes
            buff = file.read()
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        return b''  # Return an empty bytes object
    except IOError as e:
        print(f"Error: An I/O error occurred while reading the file: {e}")
        return b''  # Return an empty bytes object

    return buff


def master(count: int = 1):
    """Uses all 3 levels of the TX FIFO to send a stream of data

    :param int count: how many times to transmit the stream of data.
    """
    radio.stopListening()  # put radio in TX mode
    radio.flush_tx()  # clear the TX FIFO so we can use all 3 levels
    failures = 0  # keep track of manual retries
    start_timer = time.monotonic_ns()  # start timer
    
    for multiplier in range(count):  # repeat transmit the same data stream
        file_buff = read_file()
        length = len(file_buff)
        num_packets = math.ceil(length / SIZE)
        i = 0

        while i <= num_packets:  # cycle through all the payloads
            header = struct.pack('BB', i, num_packets) # HEADER: PACKET_ID, LENGTH OF TX
            buffer = header + file_buff[i*SIZE:SIZE*i+SIZE]
            
            if not radio.writeFast(buffer):  # transmission failed
                failures += 1  # increment manual retry count
                radio.reUseTX()  # resend payload in top level of TX FIFO
            else:  # transmission succeeded
                i += 1
                
    while not radio.writeFast(EOT):  # send EOT special packet
            radio.reUseTX()  # resend payload in top level of TX FIFO
                
    end_timer = time.monotonic_ns()  # end timer to know how much time it took to Tx
    print(
        f"Time to transmit data = {(end_timer - start_timer) / 1000} us.",
        f"Detected {failures} failures.",
    )


def slave():
    """Listen for any payloads and print them out (suffixed with received
    counter)

    :param int timeout: The number of seconds to wait (with no transmission)
        until exiting function.
    """
    radio.startListening()  # put radio in RX mode
    count = 0  # keep track of the number of received payloads
    receive_payload = b''
    last_packet = -1
    while True:
        if radio.available():
            # retrieve the received packet's payload
            new_payload = radio.read(radio.payloadSize)  # Read the new payload
            packet_id = int(new_payload[0]) # First byte is PACKET_ID
            num_packets = int(new_payload[1]) # Second byte is length of Tx in packets
            print("Received packet:", packet_id, "of", num_packets)	
            
            if count == num_packets: # If we have received all packets we quit
                print("End of transmission received. Leaving RX role")
                break
                
            receive_payload += new_payload
            count += 1

    file_path = 'output_file.txt'
    try:
        with open(file_path, 'w') as file: # Investigate if UNICODE vs write simply as bytes
            file.write(receive_payload.decode('utf-8'))
    except IOError as e:
        print(f"Error: An I/O error occurred while writing to the file: {e}")

    # recommended behavior is to keep in TX mode while idle
    radio.stopListening()  # put the radio in TX mode


def set_role() -> bool:
    """Set the role using stdin stream. Role args can be specified using space
    delimiters (e.g. 'R 10' calls `slave(10)` & 'T 3' calls `master(3)`)

    :return:
        - True when role is complete & app should continue running.
        - False when app should exit
    """
    user_input = (
        input(
            "*** Enter 'R' for receiver role.\n"
            "*** Enter 'T' for transmitter role.\n"
            "*** Enter 'Q' to quit example.\n"
        )
        or "?"
    )
    user_input = user_input.split()
    if user_input[0].upper().startswith("R"):
        if len(user_input) > 1:
            slave()
        else:
            slave()
        return True
    if user_input[0].upper().startswith("T"):
        if len(user_input) > 1:
            master(int(user_input[1]))
        else:
            master()
        return True
    if user_input[0].upper().startswith("Q"):
        radio.powerDown()
        return False
    print(user_input[0], "is an unrecognized input. Please try again.")
    return set_role()


if __name__ == "__main__":
    try:
        while set_role():
            pass  # continue example until 'Q' is entered
    except KeyboardInterrupt:
        print(" Keyboard Interrupt detected. Powering down radio.")
        radio.powerDown()
else:
    print("    Run slave() on receiver\n    Run master() on transmitter")