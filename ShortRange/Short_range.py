import sys
sys.path.append('/usr/local/lib/python3.11/dist-packages/RF24-1.4.10-py3.11-linux-aarch64.egg')
import time
import math
from RF24 import RF24, RF24_PA_LOW, RF24_DRIVER, RF24_PA_MAX, RF24_2MBPS, RF24_1MBPS, RF24_CRC_16
from read_USB import *
from compression import compress_data, decompress_data
import struct
from typing import List

radio = None

MAX_SIZE = 32  # this is the default maximum payload size
HEADER_SIZE = 1 # ID of the message
PAYLOAD_SIZE = MAX_SIZE - HEADER_SIZE
PING_SIZE = 4 # [PING_ID,chunk_ID(2Bytes),total_packets]

BURST_SIZE = 6

PING_ID = 0 # Has to be zero as message ID start at 1, to be able to differenciate between packet types
PING_FINISH_TX_ID = 0xFFFF

TIMEOUT_ACK_LOST = 15 # TODO: Test to ajust the parameter (Master wait the
                    # reception of the ACK before retransmission in ms)
TIMEOUT_PING_LOST = 10 # TODO: In theory has to be smaller than ACK_LOST
TIMEOUT_ACK = 0.3 # Puesto totalmente a ojo tiene que ser el tiempo que 
                            # tarda en recivir todo el burst

chunk_current_ID = -1

PACKET_BUFF = [] # List of chunks, each elements contain a list with a 
                # tupla as element (packetID,payload)
MESSAGE_BUFF = [] # Contain the list of messages of one chunk

def init_radio():
    global radio
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

    radio_number = bool(
        int(input("Which mode? Enter Tx '0' or Rx '1' -> ") or 0)
    )

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

    # for debugging, we have 2 options that # print a large block of details
    # (smaller) function that # prints raw register values
    # radio.# printDetails()
    # (larger) function that # prints human readable data
    # radio.# printPrettyDetails()

    try:
        if radio_number == 1:
            slave()
        else:
            master()
        radio.powerDown()
    except KeyboardInterrupt:
        # print(" Keyboard Interrupt detected. Powering down radio.")
        radio.powerDown()

# ------------ MASTER FUNCTIONS ------------

def build_packets(data: List[bytes]):
    global PACKET_BUFF
    PACKET_BUFF = [[]] * len(data)

    for chunk_index, chunk in enumerate(data):
        length = len(chunk)
        num_packets = math.ceil(length / PAYLOAD_SIZE)
        print(f"TOTAL PACK {num_packets} CHUNK {chunk_index}")
        messages = []
        for i in range(1, num_packets + 1):
            header = struct.pack('B', i)
            payload = chunk[(i-1) * PAYLOAD_SIZE:PAYLOAD_SIZE * i]
            messages.append((i,header + payload))
        PACKET_BUFF[chunk_index] = messages

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

    MESSAGE_BUFF = PACKET_BUFF[chunk_ID]
    count = 0
    while len(MESSAGE_BUFF) !=0:
        burst = MESSAGE_BUFF[:BURST_SIZE]
        send_burst(burst,len(burst))
        wait_ack(count)
        count+=1


def wait_ack(packet):
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
                if received[0] != PING_ID:
                    for _,ack_ID in enumerate(received):
                        # print(f"ACK received {ack_ID}")
                        MESSAGE_BUFF = [element for element in MESSAGE_BUFF if element[0] != ack_ID]
                else:
                    print("Received PING when not expected, discart")
            else:
                break
    else:
        print(f"No response received. TIMEOUT_ACK {packet}")

def ping_master(chunk_ID,num_packets):
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
    while True:
        if radio.write(buffer):
            print("Sent ping")
            radio.startListening()  # put radio in RX mode
            timeout = time.monotonic() * 1000 + TIMEOUT_PING_LOST  # use 200 ms timeout
            while not radio.available() and time.monotonic() * 1000 < timeout:
                pass
            radio.stopListening()  # put radio in TX mode

            has_payload, pipe_number = radio.available_pipe()
            if has_payload:
                # grab the incoming payload
                received = radio.read(PING_SIZE)
                if (received[0] == PING_ID) and (int.from_bytes(received[1:3], byteorder='big') == chunk_ID):
                    break
                else:
                    print(f"Incorrect chunk received {received[0]} {int.from_bytes(received[1:3], byteorder='big')}")
            else:
                print("No response received.")
        else:
            print("Transmission failed or timed out")
    # print(f"Ping chunk recieved {chunk_ID}.")

def master():
    global PACKET_BUFF
    file_buff = read_file()
    compressed_data = compress_data(file_buff)
    build_packets(compressed_data)
    start_time = time.time()  # Record the start time

    for i in range(len(compressed_data)):
        ping_master(i,len(PACKET_BUFF[i]))
        send_chunck(i)

    end_time = time.time()    # Record the end time
    execution_time = end_time - start_time  # Calculate the difference
    print(f"The transmission took {execution_time:.2f} s.")

    ping_master(PING_FINISH_TX_ID,0)


# ------------ SLAVE FUNCTIONS ------------

def ping_slave(payload):
    """
        Ping to sichronize both nodes before starting the transmission of a chunk
    """

    global chunk_current_ID
    global radio

    chunk_revc = int.from_bytes(payload[1:3], byteorder='big')  

    if (chunk_revc == (chunk_current_ID + 1)):
        radio.stopListening()  # put radio in TX mode
        radio.writeFast(payload)  # load response into TX FIFO
        radio.txStandBy(0)
        radio.startListening()  # put radio back in RX mode
        chunk_current_ID += 1
        return payload[3]
    elif (chunk_revc == PING_FINISH_TX_ID):
        radio.stopListening()  # put radio in TX mode
        radio.writeFast(payload)  # load response into TX FIFO
        radio.txStandBy(0)
        # keep retrying to send response for 150 milliseconds
        radio.startListening()  # put radio back in RX mode
        return 0
    else:
        print(f"Not expected chunk ID rev:{payload[0]}, exp:{(chunk_current_ID + 1)}")



def slave():
    global radio
    global chunk_current_ID
    radio.startListening()  # put radio in RX mode
    start_timer = time.monotonic()
    count_burst = 0
    received_packets = []
    ack_payload = b''
    chunk_buff = []

    while True:
        has_payload, pipe_number = radio.available_pipe()
        if has_payload:
            payload_size = radio.getDynamicPayloadSize()
            if payload_size >= 2:
                received = radio.read(payload_size)  # fetch the payload

                if received[0] == PING_ID:
                    # Respond to the ping
                    radio.stopListening()
                    radio.writeFast(received)
                    radio.txStandBy(0)
                    radio.startListening()
                    # Continue processing

                    chunk_ID = int.from_bytes(received[1:3], byteorder='big')
                    if chunk_ID  == (chunk_current_ID+1) or chunk_ID == PING_FINISH_TX_ID:

                        chunk_current_ID += 1

                        if chunk_current_ID != 0: # skip the first PING, no data to decompress
                            print(f"Finish chunk {int.from_bytes(received[1:3], byteorder='big')  }")
                            i = 0
                            for pak in received_packets:
                                if len(pak) !=31 and i !=0:
                                    print(i)
                                    i+=1
                                    print(pack)
                            chunk_buff.append(b''.join(received_packets[1:]))

                        if chunk_ID == PING_FINISH_TX_ID:# Transmission finished
                            file_path = '_file.txt'
                            for compress_chunk in chunk_buff:
                                decompress_data(compress_chunk, file_path)
                            break

                        received_packets = [bytes([0])] * (received[3] + 1)

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

    # recommended behavior is to keep in TX mode while idle
    radio.stopListening()  # put the radio in TX mode

# ------------------------------------------

if __name__ == "__main__":
    init_radio()
else:
    print("    Run slave() on receiver\n    Run master() on transmitter")
