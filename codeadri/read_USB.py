import subprocess
import time
import os
import shutil
from datetime import datetime

def get_usb_drives():
    """Get a list of currently mounted USB drives."""
    result = subprocess.run(['lsblk', '-o', 'NAME,MOUNTPOINT'], capture_output=True, text=True)
    usb_drives = []

    for line in result.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2:
            name, mountpoint = parts
            if mountpoint.startswith('/media/'):
                usb_drives.append((name, mountpoint))

    return usb_drives

def list_contents(mountpoint):
    """List the contents of the given mountpoint."""
    try:
        contents = os.listdir(mountpoint)
        return contents
    except Exception as e:
        print(f"Error reading contents of {mountpoint}: {e}")
        return []

def select_file_from_usb(drive_mountpoint):
    """List contents of the USB drive and allow user to select a file."""
    contents = list_contents(drive_mountpoint)

    if contents:
        print(f"Contents of {drive_mountpoint}:")
        for index, item in enumerate(contents):
            print(f"{index}: {item}")

        while True:
            try:
                selected_index = int(input("Select a file from the above list (input num): "))
                if 0 <= selected_index < len(contents):
                    full_path = os.path.join(drive_mountpoint, contents[selected_index])
                    print(f"Path {full_path}")
                    return full_path
                else:
                    print("Invalid index. Please select a valid number.")
            except ValueError:
                print("Invalid input. Please enter a number.")
    else:
        print("No files found in the USB drive.")
        return None
    


def print_file_content(file_path):
    """Print the content of the file at the given path."""
    try:
        with open(file_path, 'rb') as file:
            content = file.read()
            print(f"Content of {file_path}:\n{content}")
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")

def get_file_usb():
    """Main function to monitor USB drives and select a file."""
    print("Looking for USB driver")

    try:
        while True:

            current_drives = get_usb_drives()

            if len(current_drives) == 1:
                drive = current_drives[0]
                print(f"USB drive connected: {drive[0]} mounted at {drive[1]}")
                selected_file_path = select_file_from_usb(drive[1])

                if selected_file_path:
                    print(f"Selected file path: {selected_file_path}")
                    return selected_file_path
                else:
                    print("No file selected or file not found.")

            time.sleep(1)

    except KeyboardInterrupt:
        print("Monitoring stopped.")

def get_file_usb_lcd():
    """Main function to monitor USB drives and select a file."""
    print("Looking for USB driver")

    try:
        while True:
            current_drives = get_usb_drives()
            if len(current_drives) == 1:
                drive = current_drives[0]
                print(f"USB drive connected: {drive[0]} mounted at {drive[1]}")
                return drive[1]

            time.sleep(1)

    except KeyboardInterrupt:
        print("Monitoring stopped.")

def save_file_USB(copy_file_path):
    """Save a file to the connected USB drive with the current date in the filename."""
    print("Looking for USB driver")

    try:
        while True:
            current_drives = get_usb_drives()

            if len(current_drives) == 1:
                drive = current_drives[0]
                print(f"USB drive connected: {drive[0]} mounted at {drive[1]}")

                # Get the current date and format it
                current_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                # Create a new filename with the current date
                base_name = os.path.basename(copy_file_path)
                new_file_name = f"{current_date}_{base_name}"
                destination_path = os.path.join(drive[1], new_file_name)

                # Copy the file to the USB drive
                shutil.copy2(copy_file_path, destination_path)
                print(f"File saved to {destination_path}")
                return destination_path

            time.sleep(1)

    except KeyboardInterrupt:
        print("Monitoring stopped.")
    except Exception as e:
        print(f"An error occurred: {e}")

def read_file(file_path: str) -> bytes:
    """Returns a dynamically created payloads

    :param int buf_iter: The position of the payload in the data stream
    """
    print(file_path)
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

if __name__ == "__main__":
    path = get_file_usb()
    save_file_USB(path)