import sys
sys.path.append('/usr/local/lib/python3.11/dist-packages/RF24-1.4.10-py3.11-linux-aarch64.egg')
import time
import math
from RF24 import RF24, RF24_PA_LOW, RF24_DRIVER, RF24_PA_MAX, RF24_2MBPS, RF24_1MBPS, RF24_CRC_16
from read_USB import *
from compression import compress_data, decompress_data
import struct
from typing import List
import RPi.GPIO as GPIO
import threading

radio = None

NAV_BUTTON_PIN = 23
SELECT_BUTTON_PIN = 24
finish_transmission = False

def button_monitor():
    while True:
        if GPIO.input(NAV_BUTTON_PIN) == GPIO.HIGH:
            press_start_time = time.time()

            while GPIO.input(NAV_BUTTON_PIN) == GPIO.HIGH:
                # Check if 2 seconds have passed
                if time.time() - press_start_time >= 1:
                    print("Button pressed")
                    global finish_transmission
                    finish_transmission = True
                    break  # Exit the loop after 2 seconds

        time.sleep(0.5)  # Short delay to avoid busy-waiting


MAX_SIZE = 32  # this is the default maximum payload size
HEADER_SIZE = 1 # ID of the message
PAYLOAD_SIZE = MAX_SIZE - HEADER_SIZE
PING_SIZE = 4 # [PING_ID,chunk_ID(2Bytes),total_packets]

BURST_SIZE = 2

PING_ID = 0 # Has to be zero as message ID start at 1, to be able to differenciate between packet types
PING_FINISH_TX_ID = 0xFFFF
CHUNK_ERROR = 0xFF

TIMEOUT_ACK_LOST = 25 # TODO: Test to ajust the parameter (Master wait the
                    # reception of the ACK before retransmission in ms)
TIMEOUT_PING_LOST = 10 # TODO: In theory has to be smaller than ACK_LOST
TIMEOUT_ACK = 0.3 # Puesto totalmente a ojo tiene que ser el tiempo que 
                            # tarda en recivir todo el burst

chunk_current_ID = -1

PACKET_BUFF = [] # List of chunks, each elements contain a list with a 
                # tupla as element (packetID,payload)
MESSAGE_BUFF = [] # Contain the list of messages of one chunk

def init_radio(mode):
    global radio
    global chunk_current_ID
    chunk_current_ID = -1
    global finish_transmission
    finish_transmission = False
    CSN_PIN = 0  # GPIO8 aka CE0 on SPI bus 0: /dev/spidev0.0
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

    address = [b"Tx", b"Rx"]

    radio_number = mode

    # set the Power Amplifier level to -12 dBm since this test example is
    # usually run with nRF24L01 transceivers in close proximity of each other
    radio.setPALevel(RF24_PA_LOW)
    radio.setDataRate(RF24_2MBPS)
    radio.setAutoAck(False)
    # radio.setCRCLength(RF24_CRC_16)
    radio.setAddressWidth(3)

    radio.openWritingPipe(address[radio_number])  # always uses pipe 0
    radio.openReadingPipe(1, address[not radio_number])  # using pipe 1

    radio.enableDynamicPayloads()
    radio.setChannel(86)

    # for debugging, we have 2 options that # print a large block of details
    # (smaller) function that # prints raw register values
    # radio.# printDetails()
    # (larger) function that # prints human readable data
    # radio.# printPrettyDetails()

# ------------ MASTER FUNCTIONS ------------

def build_packets(data: List[bytes]):
    global PACKET_BUFF
    PACKET_BUFF = [[]] * len(data)
    total_chunks = 0

    for chunk_index, chunk in enumerate(data):
        length = len(chunk)
        num_packets = math.ceil(length / PAYLOAD_SIZE)
        print(f"TOTAL PACK {num_packets} CHUNK {chunk_index}")
        total_chunks += num_packets
        messages = []
        for i in range(1, num_packets + 1):
            header = struct.pack('B', i)
            payload = chunk[(i-1) * PAYLOAD_SIZE:PAYLOAD_SIZE * i]
            messages.append((i,header + payload))
        PACKET_BUFF[chunk_index] = messages

    return math.ceil(total_chunks / (chunk_index + 1)), chunk_index

def send_burst(messages, length):
    global radio
    radio.stopListening()  # put radio in TX mode
    radio.flush_tx()  # clear the TX FIFO so we can use all 3 levels

    for i in range(length):
        radio.writeFast(messages[i][1])

    radio.txStandBy(0)
    radio.startListening()

# TODO: What to do if the burst don't fill completely the burst -> Repite packet?
def send_chunck(chunk_ID):
    global MESSAGE_BUFF
    global PACKET_BUFF
    global finish_transmission

    MESSAGE_BUFF = PACKET_BUFF[chunk_ID]
    count = 0
    while len(MESSAGE_BUFF) !=0 and not finish_transmission:
        burst = MESSAGE_BUFF[:BURST_SIZE]
        send_burst(burst,len(burst))
        if not wait_ack():
            count+=1
    return count


def wait_ack():
    global radio
    global MESSAGE_BUFF
    timeout = time.monotonic() * 1000 + TIMEOUT_ACK_LOST  # use 200 ms timeout
    # declare a variable to save the incoming response
    while not radio.available() and time.monotonic() * 1000 < timeout:
        pass  # wait for incoming payload or timeout
    radio.stopListening()  # put radio in TX mode

    if radio.available():
        while True:
            has_payload, pipe_number = radio.available_pipe()
            # grab the incoming payload
            if has_payload:
                ack_size = radio.getDynamicPayloadSize()
                received = radio.read(ack_size)
                try:
                    if received[0] != PING_ID:
                        for _,ack_ID in enumerate(received):
                            # print(f"ACK received {ack_ID}")
                            MESSAGE_BUFF = [element for element in MESSAGE_BUFF if element[0] != ack_ID]
                    else:
                        print("Received PING when not expected, discart")
                except:
                    print("Wrong size")
            else:
                return True
    else:
        print(f"No response received. TIMEOUT_ACK")
        return False

def ping_master(chunk_ID,num_packets, lcd):
    """
        Ping to sichronize both nodes before starting the transmission of a chunk
        chunk_ID: counter indentifying the chunk that is going to be sent
    """
    # print(f"Ping chunk send {chunk_ID}.")
    global radio
    radio.stopListening()  # put radio in TX mode
    radio.flush_tx()  # clear the TX FIFO so we can use all 3 levels
    buffer = b''
    buffer += PING_ID.to_bytes(1, 'big')
    buffer += chunk_ID.to_bytes(2, 'big')
    buffer += num_packets.to_bytes(1, 'big')
    global finish_transmission

    while not finish_transmission:
        if radio.write(buffer):
            print(f"Sent ping {chunk_ID}")
            radio.startListening()  # put radio in RX mode
            timeout = time.monotonic() * 1000 + TIMEOUT_PING_LOST  # use 200 ms timeout
            while not radio.available() and time.monotonic() * 1000 < timeout:
                pass
            radio.stopListening()  # put radio in TX mode

            try:
                has_payload, pipe_number = radio.available_pipe()
                if has_payload:
                    # grab the incoming payload
                    received = radio.read(PING_SIZE)
                    if (received[0] == PING_ID) and (int.from_bytes(received[1:3], byteorder='big') == chunk_ID):
                        if received[3] == CHUNK_ERROR:
                            # Error in compression, resend again
                            print("Error in compression, resend again chunk")
                            return False
                        return True
                    else:
                        print(f"Incorrect chunk received {received[0]} {int.from_bytes(received[1:3], byteorder='big')}")
                else:
                    print("No response received.")
            except:
                print("Wrong size")
        else:
            print("Transmission failed or timed out")
    # print(f"Ping chunk recieved {chunk_ID}.")

def master(file_buffer, lcd):
    init_radio(0)
    global PACKET_BUFF
    compressed_data, compression = compress_data(file_buffer)
    num_packets, chunk_index = build_packets(compressed_data)
    lcd.show_message_on_lcd(f"CP: {compression:.2f} PxC:{num_packets} \nChunks: {chunk_index+1}")

    monitor_thread = threading.Thread(target=button_monitor)
    monitor_thread.daemon = True  # Allow thread to exit when main program exits
    monitor_thread.start()
    global finish_transmission

    while GPIO.input(SELECT_BUTTON_PIN) == GPIO.LOW: 
        pass

    start_time = time.time()  # Record the start time

    i = 0
    lcd.show_message_on_lcd(f"Start transmission")
    ping_master(i,len(PACKET_BUFF[i]), lcd)
    while i < (len(compressed_data)-1) and not finish_transmission:
        timeout_ack = send_chunck(i)
        result = ping_master(i+1,len(PACKET_BUFF[i+1]), lcd)
        if result:
            i +=1
        lcd.show_message_on_lcd(f"Chunk {i} sent \nTimeouts {timeout_ack}")

    if not finish_transmission:
        send_chunck(i)

        end_time = time.time()    # Record the end time
        execution_time = end_time - start_time  # Calculate the difference
        print(f"The transmission took {execution_time:.2f} s.")
        lcd.show_message_on_lcd(f"Time: {execution_time:.2f}")

        while not ping_master(PING_FINISH_TX_ID,0,lcd) and not finish_transmission:
            send_chunck(i)
        radio.powerDown()
        time.sleep(10)
        lcd.show_message_on_lcd(f"(^_^)")
        time.sleep(10)
    else:
        radio.powerDown()
        lcd.show_message_on_lcd(f"Time Finish")
        time.sleep(10)

    



# ------------ SLAVE FUNCTIONS ------------

def slave(lcd):
    global radio
    global chunk_current_ID
    init_radio(1)

    file_path = "_file.txt"

    if os.path.exists(file_path):
        os.remove(file_path)  # Delete the file
        print(f"{file_path} has been deleted.")
    else:
        print(f"{file_path} does not exist.")

    monitor_thread = threading.Thread(target=button_monitor)
    monitor_thread.daemon = True  # Allow thread to exit when main program exits
    monitor_thread.start()

    radio.startListening()  # put radio in RX mode
    lcd.show_message_on_lcd("Waiting")
    start_timer = time.monotonic()
    count_burst = 0
    received_packets = []
    ack_payload = b''
    chunk_buff = []
    global finish_transmission

    while not finish_transmission:
        has_payload, pipe_number = radio.available_pipe()
        if has_payload:
            payload_size = radio.getDynamicPayloadSize()
            try:
                received = radio.read(payload_size)  # fetch the payload

                if received[0] == PING_ID:
                    chunk_ID = int.from_bytes(received[1:3], byteorder='big')
                    if chunk_ID  == (chunk_current_ID+1) or chunk_ID == PING_FINISH_TX_ID:

                        chunk_current_ID += 1

                        if chunk_current_ID != 0: # skip the first PING, no data to decompress
                            print(f"Finish chunk {int.from_bytes(received[1:3], byteorder='big')-1  }")
                            lcd.show_message_on_lcd(f"Received \n Chunk {chunk_current_ID-1}")
                            compress_chunk = b''.join(received_packets[1:])
                            result = decompress_data(compress_chunk, file_path)
                            if not result: # Error in the chunk request sent again
                                print(f"Error decompression. Transmit chunk again {chunk_current_ID-1}")
                                lcd.show_message_on_lcd(f"Resent {chunk_current_ID-1}")
                                received[3] = CHUNK_ERROR
                                chunk_current_ID -= 1
                            else:
                                received_packets = [bytes([0])] * (received[3] + 1)
                        else:
                            lcd.show_message_on_lcd(f"Transmission started :)")
                            received_packets = [bytes([0])] * (received[3] + 1)

                        if chunk_ID == PING_FINISH_TX_ID:# Transmission finished
                            # Respond to the ping
                            lcd.show_message_on_lcd("Finished")
                            for i in range(5):
                                radio.stopListening()
                                radio.writeFast(received)
                                radio.writeFast(received)
                                radio.txStandBy(0)
                                radio.startListening()
                                time.sleep(1)
                            lcd.show_message_on_lcd("Looking for USB driver")
                            save_file = save_file_USB(file_path)
                            lcd.show_message_on_lcd(f"File saved to \n{save_file}")
                            time.sleep(5)
                            lcd.show_message_on_lcd(f"(O_O)")
                            time.sleep(10)
                            # Continue processing
                            break

                    # Respond to the ping
                    radio.stopListening()
                    radio.writeFast(received)
                    radio.writeFast(received)
                    radio.txStandBy(0)
                    radio.startListening()
                    # Continue processing
                else:
                    if count_burst == 0:
                        start_timer = time.monotonic()
                    count_burst += 1

                    packet_id = received[0]
                    ack_payload += struct.pack('B', packet_id)
                    received_packets[packet_id] = received[1:]
                    lenght = len(received[1:])

                    if count_burst == BURST_SIZE or ((time.monotonic() - start_timer)*1000 > TIMEOUT_ACK):
                        # Timeout or all packets received send ACK
                        radio.stopListening()  # put radio in TX mode
                        radio.writeFast(ack_payload)
                        radio.writeFast(ack_payload)
                        radio.txStandBy(0)
                        radio.startListening()  # put radio back in RX mode

                        ack_payload = b''
                        count_burst = 0
            except:
                print("Packet wrong size")

    # recommended behavior is to keep in TX mode while idle
    radio.stopListening()  # put the radio in TX mode
    radio.powerDown()
    print("Hello")
    if finish_transmission:
        lcd.show_message_on_lcd("Transmission finished")
        time.sleep(5)
        lcd.show_message_on_lcd("Looking for USB driver")
        #Try to decompress last chunk
        compress_chunk = b''.join(received_packets[1:])
        decompress_data(compress_chunk, file_path)

        save_file = save_file_USB(file_path)
        lcd.show_message_on_lcd(f"File saved to \n{save_file}")
        time.sleep(5)
        lcd.show_message_on_lcd(f"(O_O)")
        time.sleep(10)



# ------------------------------------------

if __name__ == "__main__":
    init_radio()
else:
    print("    Run slave() on receiver\n    Run master() on transmitter")
