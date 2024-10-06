from pyrf24 import RF24, RF24_PA_LOW, RF24_DRIVER
import os
from bitarray import bitarray

CSN_PIN = 0 # The pin attached to Chip Select in RF module
CE_PIN = 13 # The pin attached to Chip Enable in RF module

radio = RF24(CE_PIN, CSN_PIN)
if not radio.begin():
    raise RuntimeError("Unable to initialize radio")


address = "010" # radio address

############## CONFIG PARAMETERS ##################
radio.setChannel()
radio.setPayloadSize()
radio.setPAlevel() #Desired power amplifier level (int 0-3) -> (-18, -12, -6, 0)dBm
radio.setDataRate() #Specify data rate (int 0-2) -> (1Mbps, 2Mbps, 250kbps)
radio.setCRCLength() #Specify CRC length (int 0-2) -> (disable, 8bit, 16bit)
radio.setAutoACK()
chunk_size = 32 #Amount of data to put into a single packet in bytes
####################################################

radio.openWritingPipe(address)
payload =[0.0]



def master():
    """
    Controls the transmission of data read from a file using a radio module.

    This function performs the following steps:
    1. Stops the radio from listening to put it in TX mode.
    2. Reads the contents of 'prueba.txt' located in the same directory as the script.
    3. Splits the file content into chunks of a specified size.
    4. Transmits each chunk using the radio module, retrying if the transmission fails.

    Note:
        - The `radio` object should be properly initialized and configured before calling this function.

    Raises:
        FileNotFoundError: If 'prueba.txt' does not exist in the specified directory.
        IOError: If there is an error reading the file.
    """
    radio.stopListening()  # put radio in TX mode
    # Read the file 'prueba.txt'
    file_path = os.path.join(os.path.dirname(__file__), 'prueba.txt')
    with open(file_path, 'r') as file:
        bitstream = file.read()
        # Now we split the array into chunks of the specified size
        chunks = [bitstream[i:i + chunk_size] for i in range(0, len(bitstream), chunk_size)]

    for chunk, i in enumerate(chunks):
        while True:
            result = radio.write(chunk)

            if not result:
                print("     Transmission failed or time out, retrying")
            else:
                print("Chunk {}/{} transmitted successfully".format(i + 1, len(chunks)))
                break # Exit loop once transmission has been achieved

    print("Transmission accomplished!")

if __name__ == "__main__":
    try:
        master()
    except KeyboardInterrupt:
        print("Ending transmission, interrupt detected")
        radio.powerDown()
