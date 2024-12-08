import zlib
import os
from typing import List
import argparse
import math

def compress_data(data: bytes, split = 30, size_payload = 31, max_pack = 255) -> List[bytes]:
    """Takes the text file and compreses it using zlib compression algorithm
    into blocks of SPLIT_SIZE KILOBYTES.

    :param bytes data: The data to compress
    :param int SPLIT_SIZE: The size of the chunks to split the data into in **KB**
    :return: List with the compressed chunks
    """
    finish = False
    while not finish:
        finish = True
        SPLIT_SIZE = split * 1024  
        compressed_data = []
        for i in range(0, len(data), SPLIT_SIZE):
            try:
                split_data = data[i:i + SPLIT_SIZE] # Take SPLIT_SIZE bytes
                compress_chunk = zlib.compress(split_data)
                length = len(compress_chunk)
                num_packets = math.ceil(length / size_payload)
                if num_packets > max_pack:
                    split -= 1 #Reduce the size of the chunk
                    finish = False
                    break
                compressed_data.append(compress_chunk) # Compress the data
            except zlib.error as e:
                print(f"Error: An error occurred while compressing the data: {e}")
                return []  # Return an empty bytes object

    print("Data split into {} blocks".format(len(compressed_data)))
    print("Original size: {} bytes".format(len(data)))
    print("Compressed size: {} bytes".format(sum([len(chunk) for chunk in compressed_data])))
    print("Compression ratio: {:.2f}%".format((1 - sum([len(chunk) for chunk in compressed_data]) / len(data)) * 100))
    compression = (1 - sum([len(chunk) for chunk in compressed_data]) / len(data)) * 100
    return compressed_data, compression

""" def decompress_data(data: bytes) -> bytes:
    try:
        decompressed_data = zlib.decompress(data)
    except zlib.error as e:
        print(f"Error: An error occurred while decompressing the data: {e}")
        return b""  # Return an empty bytes object
    return decompressed_data """

def decompress_data(data: bytes, filepath) -> bytes:
    try:
        decompressed_data = zlib.decompress(data)
        with open(filepath, "ab") as f:
            f.write(decompressed_data)
        return True
    except zlib.error as e:
        print(f"Error: An error occurred while decompressing the data: {e}")
        return False

def find_differences(file1_path, file2_path):
    with open(file1_path, "rb") as f1, open(file2_path, "rb") as f2:
        file1_data = f1.read()
        file2_data = f2.read()

    min_length = min(len(file1_data), len(file2_data))
    differences = []

    for i in range(min_length):
        if file1_data[i] != file2_data[i]:
            differences.append((i, file1_data[i], file2_data[i]))

    if len(file1_data) != len(file2_data):
        differences.append(("length", len(file1_data), len(file2_data)))

    return differences

def are_files_different(file1, file2):
    with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
        for line1, line2 in zip(f1, f2):
            if line1 != line2:
                return True
    return False

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description="Find differences between two files.")
    parser.add_argument("file1", help="Path to the first file")
    parser.add_argument("file2", help="Path to the second file")
    
    # Parse the arguments
    args = parser.parse_args()
    
    # Call the function with the provided arguments
    if are_files_different(args.file1, args.file2):
        print("The files are different.")
    else:
        print("The files are the same.")
