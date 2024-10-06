import zlib
import time

# Read the contents of the file 'prueba.txt'
file_path = 'prueba.txt'
with open(file_path, 'rb') as file:
    original_data = file.read()

# Measure the time taken to compress the file content
start_time = time.time()
compressed_data = zlib.compress(original_data)
end_time = time.time()
compression_time = end_time - start_time

print(f"Compression Time: {compression_time:.6f} seconds")

# Measure the time taken to decompress the file content
start_time = time.time()
decompressed_data = zlib.decompress(compressed_data)
end_time = time.time()
decompression_time = end_time - start_time

# Verify if decompression yields the original data
assert original_data == decompressed_data
print(f"Decompression Time: {decompression_time:.6f} seconds")

# Size comparison
original_size = len(original_data)
compressed_size = len(compressed_data)
decompressed_size = len(decompressed_data)

print(f"Original Size: {original_size} bytes")
print(f"Compressed Size: {compressed_size} bytes")
print(f"Decompressed Size: {decompressed_size} bytes")

# Compression ratio
compression_ratio = compressed_size / decompressed_size if decompressed_size != 0 else float('inf')
print(f"Compression Ratio: {compression_ratio:.2f}")