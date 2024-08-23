# To run the test:
# python test_writing_speed.py
import tifffile as tiff
import numpy as np
import os
import time
import sys

def test_write_large_TIFF_stack():
    disk = input("Enter the disk where you want to write, with at least 50 GB free space (e.g., D:): ")
    filepath = f"{disk}/large_stack.tif"
    tiff_writer = tiff.TiffWriter(filepath, imagej=True)
    NZ, NY, NX = 5000, 2048, 2048
    print(f"Writing a {NX}x{NY}x{NZ} stack of random uint16 values to {filepath}")

    # Write the stack to a TIFF file
    start_time = time.time()
    for iz in range(NZ):
        plane = np.random.randint(0, 65535, size=(NY, NX), dtype=np.uint16)
        print(f"Writing plane {iz+1} of {NZ}")
        tiff_writer.write(plane[np.newaxis,...], contiguous=True)
    tiff_writer.close()
    assert os.path.exists(filepath) # Verify if the file was written successfully
    end_time = time.time()

    # Calculate and print the framerate
    time_per_stack = end_time - start_time
    framerate = NZ / time_per_stack
    print(f"TIFF average writing speed: {int(sys.getsizeof(plane) * NZ / time_per_stack / 1e6)} MB/s")
    print(f"Frame rate: {framerate:1.2f} planes per second")

    # Clean up the files
    #os.remove(filepath)
    print(f"TIFF file {filepath} cleaned up successfully")

test_write_large_TIFF_stack()