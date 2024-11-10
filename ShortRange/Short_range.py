import time
import math
from RF24 import RF24, RF24_PA_LOW, RF24_DRIVER
from read_USB import *
from compression import compress_data, decompress_data
import struct
from typing import List

radio = None

MAX_SIZE = 32  # this is the default maximum payload size
HEADER_SIZE = 1 # ID of the message
PAYLOAD_SIZE = MAX_SIZE - HEADER_SIZE
BURST_SIZE = 3
# ACK_SIZE = BURST_SIZE # TODO: Not used by the moment
PING_ID = 0 # Has to be zero as message ID start at 1, to be able to differenciate between packet types
PING_FINISH_TX_ID = 255

PING_SIZE = 3 # [PING_ID,chunk_ID,total_packets]
TIMEOUT_BURST = 1000 # 1 second (Time Tx before switch to Rx)
TIMEOUT_ACK_LOST = 1000 # TODO: Test to ajust the parameter (Master wait the
                    # reception of the ACK before retransmission in ms)
TIMEOUT_PING_LOST = 1000 # TODO: In theory has to be smaller than ACK_LOST
TIMEOUT_ACK = 1*BURST_SIZE # Puesto totalmente a ojo tiene que ser el tiempo que 
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

    address = [b"TeamA", b"Winner"]

    radio_number = bool(
        int(input("Which mode? Enter Tx '0' or Rx '1' -> ") or 0)
    )

    # set the Power Amplifier level to -12 dBm since this test example is
    # usually run with nRF24L01 transceivers in close proximity of each other
    radio.setPALevel(RF24_PA_LOW)  # RF24_PA_MAX is default

    # set the TX address of the RX node into the TX pipe
    radio.openWritingPipe(address[radio_number])  # always uses pipe 0

    # set the RX address of the TX node into a RX pipe
    radio.openReadingPipe(1, address[not radio_number])  # using pipe 1

    # To save time during transmission, we'll set the payload size to be only
    # what we need, and only update it when transmitting a shoter paket.
    #radio.payloadSize = PING_SIZE TODO optimize by not dynamic payload
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
    # print(f"TOTAL CHUNKS {len(data)}")
    PACKET_BUFF = [[]] * len(data)
    # print(f"TOTAL CHUNKS {len(PACKET_BUFF)}")

    for chunk_index, chunk in enumerate(data):
        length = len(chunk)
        num_packets = math.ceil(length / PAYLOAD_SIZE)
        # print(f"TOTAL PACK {num_packets} CHUNK {chunk_index}")
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
        # Handle overflow: wait for FIFO to clear or retry
        while not radio.writeFast(messages[i][1]):
            # If function return False it means that the FIFO queue
            # have overflow, wait for FIFO to clear and retry
            time.sleep(0.01)
        # print(f"Packet sent: {messages[i][0]}")

    # Last packet ajust the lenght of the payload transmited
    # TODO: if last packet ajust ()
    # while not radio.writeFast(messages[i]):
    #         # If function return False it means that the FIFO queue
    #         # have overflow, wait for FIFO to clear and retry
    #         time.sleep(0.01)
    #     # print(f"Packet sent: {messages[i]}")

    success = radio.txStandBy(TIMEOUT_BURST, True); # 1 second timeout, start in TX mode
    
    if success:
        # Transmission was successful, now switch to RX mode
        radio.startListening()
    else:
        # print("Algo falla, y nose")

# TODO: What to do if the burst don't fill completely the burst -> Repite packet?
def send_chunck(chunk_ID):
    global MESSAGE_BUFF
    global PACKET_BUFF
    # Do thing here, then send one burst
    MESSAGE_BUFF = PACKET_BUFF[chunk_ID]

    while len(MESSAGE_BUFF) !=0:
        burst = MESSAGE_BUFF[:3]
        send_burst(burst,len(burst))
        wait_ack()
    
    # print(f"Finish sending CHUNCK {chunk_ID}")

def wait_ack():
    global radio
    global MESSAGE_BUFF
    timeout = time.monotonic() * 1000 + TIMEOUT_ACK_LOST  # use 200 ms timeout
    # declare a variable to save the incoming response
    while not radio.available() and time.monotonic() * 1000 < timeout:
        pass  # wait for incoming payload or timeout
    radio.stopListening()  # put radio in TX mode

    # print("ACK received")
    has_payload, pipe_number = radio.available_pipe()
    if has_payload:
        # grab the incoming payload
        ack_size = radio.getDynamicPayloadSize()
        received = radio.read(ack_size)
        if received[0] != PING_ID:
            for _,ack_ID in enumerate(received):
                # print(f"ACK received {ack_ID}")
                MESSAGE_BUFF = [element for element in MESSAGE_BUFF if element[0] != ack_ID]
        else:
            # print("Received PING when not expected, discart")
    else:
        # print("No response received. TIMEOUT_ACK")

def ping_master(chunk_ID,num_packets):
    """
        Ping to sichronize both nodes before starting the transmission of a chunk
        chunk_ID: counter indentifying the chunk that is going to be sent
    """
    # print(f"Ping chunk send {chunk_ID}.")
    global radio
    radio.stopListening()  # put radio in TX mode
    radio.flush_tx()  # clear the TX FIFO so we can use all 3 levels
    buffer = struct.pack('BBB', PING_ID, chunk_ID,num_packets)
    while True:
        if radio.write(buffer):
            radio.startListening()  # put radio in RX mode
            timeout = time.monotonic() * 1000 + TIMEOUT_PING_LOST  # use 200 ms timeout
            while not radio.available() and time.monotonic() * 1000 < timeout:
                pass
            radio.stopListening()  # put radio in TX mode

            has_payload, pipe_number = radio.available_pipe()
            if has_payload:
                # grab the incoming payload
                received = radio.read(PING_SIZE)
                if (received[0] == PING_ID) and (received[1] == chunk_ID):
                    break
                else:
                    # print(f"Incorrect chunk received {received[0]} {received[1]}")
            else:
                # print("No response received.")
        else:
            # print("Transmission failed or timed out")
    # print(f"Ping chunk recieved {chunk_ID}.")

def master():
    global PACKET_BUFF
    file_buff = read_file()
    compressed_data = compress_data(file_buff)
    build_packets(compressed_data)
    for i in range(len(compressed_data)):
        ping_master(i,len(PACKET_BUFF[i]))
        send_chunck(i)
    ping_master(PING_FINISH_TX_ID,0)


# ------------ SLAVE FUNCTIONS ------------

def ping_slave(payload):
    """
        Ping to sichronize both nodes before starting the transmission of a chunk
    """

    global chunk_current_ID
    global radio

    if (payload[1] == (chunk_current_ID + 1)):
        radio.stopListening()  # put radio in TX mode
        radio.writeFast(payload)  # load response into TX FIFO
        # keep retrying to send response for 150 milliseconds
        radio.txStandBy(150)
        radio.startListening()  # put radio back in RX mode
        chunk_current_ID += 1
        return payload[2]
    elif (payload[1] == PING_FINISH_TX_ID):
        radio.stopListening()  # put radio in TX mode
        radio.writeFast(payload)  # load response into TX FIFO
        # keep retrying to send response for 150 milliseconds
        radio.txStandBy(150)
        radio.startListening()  # put radio back in RX mode
        return 0
    else:
        # print(f"Not expected chunk ID rev:{payload[0]}, exp:{(chunk_current_ID + 1)}")



def slave():
    global radio
    global chunk_current_ID
    radio.startListening()  # put radio in RX mode
    start_timer = time.monotonic()
    count_burst = 0
    received_packets = []
    total_expected_packets = 0
    ack_payload = b''

    while True:
        has_payload, pipe_number = radio.available_pipe()
        if has_payload:
            payload_size = radio.getDynamicPayloadSize()
            received = radio.read(payload_size)  # fetch the payload
            # print(f"Revec pay {received}")

            if received[0] == PING_ID and (received[1] == (chunk_current_ID+1) or received[1] == PING_FINISH_TX_ID):
                # print(f"Revec PING")
                if total_expected_packets != 0: # skip the first PING, no data to decompress
                    # print(f"Finish chunk {received[1]}")
                    #Process block
                    compress_chunk = b''.join(received_packets[1:])
                    file_path = '_file.txt'
                    decompress_data(compress_chunk, file_path)

                total_expected_packets = ping_slave(received)
                # print(f"expected packets {total_expected_packets}")
                if total_expected_packets == 0:# Transmission finished
                    break
                received_packets = [bytes([0])] * (total_expected_packets + 1)
            elif received[0] == PING_ID:
                radio.stopListening()  # put radio in TX mode
                radio.writeFast(received)  # load response into TX FIFO
                # keep retrying to send response for 150 milliseconds
                radio.txStandBy(150)
                radio.startListening()  # put radio back in RX mode
            else:
                if count_burst == 0:
                    start_timer = time.monotonic()
                count_burst += 1

                packet_id = received[0]
                ack_payload += struct.pack('B', packet_id)
                received_packets[packet_id] = received[1:]
                # print(f"Received packet: Chunk {chunk_current_ID}, Packet {packet_id}")

                if count_burst == BURST_SIZE or ((time.monotonic() - start_timer) > TIMEOUT_ACK and not start_burst):
                    # Timeout of all packets received send ACK
                    radio.stopListening()  # put radio in TX mode
                    radio.writeFast(ack_payload)
                    radio.txStandBy(150)
                    radio.startListening()  # put radio back in RX mode

                    ack_payload = b''
                    count_burst = 0

    # recommended behavior is to keep in TX mode while idle
    radio.stopListening()  # put the radio in TX mode

# ------------------------------------------

if __name__ == "__main__":
    init_radio()
else:
    # print("    Run slave() on receiver\n    Run master() on transmitter")
