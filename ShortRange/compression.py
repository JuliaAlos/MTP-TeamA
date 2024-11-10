import zlib 
import os
from typing import List

def compress_data(data: bytes, split = 10) -> List[bytes]:
    """Takes the text file and compreses it using zlib compression algorithm
    into blocks of SPLIT_SIZE KILOBYTES.

    :param bytes data: The data to compress
    :param int SPLIT_SIZE: The size of the chunks to split the data into in **KB**
    :return: List with the compressed chunks
    """

    SPLIT_SIZE = split * 1024  
    compressed_data = []
    for i in range(0, len(data), SPLIT_SIZE):
        try:
            split_data = data[i:i + SPLIT_SIZE] # Take SPLIT_SIZE bytes
            compressed_data.append(zlib.compress(split_data)) # Compress the data
        except zlib.error as e:
            print(f"Error: An error occurred while compressing the data: {e}")
            return []  # Return an empty bytes object
    print("Data split into {} blocks".format(len(compressed_data)))
    print("Original size: {} bytes".format(len(data)))
    print("Compressed size: {} bytes".format(sum([len(chunk) for chunk in compressed_data])))
    print("Compression ratio: {:.2f}%".format((1 - sum([len(chunk) for chunk in compressed_data]) / len(data)) * 100))
    return compressed_data

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



if __name__ == "__main__":
    FILE_PATH = "file_test.txt"
    with open(FILE_PATH, "rb") as f:
        data = f.read()
        f.close()
    compressed_data = compress_data(data)
    filepath = "decompressed.txt"
    if os.path.exists(filepath):
        os.remove(filepath)
    for i, chunk in enumerate(compressed_data):
        print("Decompressing chunk {}...".format(i))
        success = decompress_data(chunk, filepath)
        print(" Success: {}".format(success))

    "assess that the decompressed file is the same as the original"
    differences = find_differences(FILE_PATH, filepath)

    if differences:
        print("Differences found:")
        for diff in differences:
            print(diff)
    else:
        print("No differences found in the decompressed file")
