# MTP-TeamA

## Summary table
- **Microcontroller**: Raspberry Pi Zero 2 W
- **Operating System**: Raspberry Pi OS
- **Transciever**: nRF24L01
- **Programming language**: Python

## Connecting to the Raspberry Pi
You can connect to the Raspberry Pi using SSH.

### Local Connection
For a local connection use the following command from your terminal:
```bash
ssh admin@TeamA-1.local
```
or
```bash
ssh admin@TeamA-2.local
```
With password: `adminTeamA`


### Remote Connection
For a remote connection navigate to this [URL](https://connect.raspberrypi.com/devices)
- Email: `jalos24d@gmail.com`
- Password: `adminTeamA`
  
Navigate to Devices and click on Connect to the desired device to open the terminal.

## Communicating with the nRF24L01
To communicate with the nRF24L01 transceiver, we will be using the following library:
- [RF24 Library](https://github.com/nRF24/RF24)

How to install it and make it work is explained below.

## Pinout 
Transciever Module:

![image](https://github.com/user-attachments/assets/a5ab8d1a-b110-4e0c-92b2-be503d2085ef)


Raspberry:

![image](https://github.com/user-attachments/assets/20f36992-9a35-421e-a23b-d12599f68fc9)


[Pinout](https://pinout.xyz/pinout/3v3_power)


## Tasks
- [x] Install OS & Set up.
- [x] Read file from USB: Detect when an USB device has been connected and read the content of the .txt file.
- [x] Ping with the tranciever: Enable the communication with the nRF24 module.
- [x] Enabling LCD display.
- [x] Automatic start python code.

----
# Completed Tasks (Explanation for traceability)

## Task: Install OS & Set up
The installed OS is Raspberry Pi OS Lite, to improved performance on the device.
Installation Process following this [Tutorial](https://www.youtube.com/watch?v=uG8bX8IdBVs):
- Flash the OS image to the microSD card.
- Connect to the Raspberry Pi via SSH using the local connection method described above.
  
Post-Installation Steps. After connecting, update the software with the following commands:
```bash
admin@TeamA-1:~ $ sudo apt update
admin@TeamA-1:~ $ sudo apt upgrade
```
Install service to connect remotely:
```bash
admin@TeamA-1:~ $ sudo apt install rpi-connect-lite
```
To automatically start this service every time that the device restart:
```bash
admin@TeamA-1:~ $ systemctl --user start rpi-connect
```
Signin for remote access:
```bash
admin@TeamA-1:~ $ rpi-connect signin
```
## Enabling SPI bus (same for I2C)
```bash
admin@TeamA-1:~ $ sudo raspi-config
```
Navigate to the Interfacing Options menu:

Use the arrow keys to navigate to the option labeled Interfacing Options and press Enter.

Select SPI:

In the Interfacing Options menu, select the option SPI (Serial Peripheral Interface) and press Enter.

Enable SPI:

When prompted to enable the SPI interface, select Yes.

Press Finish
Reboot
```bash
admin@TeamA-1:~ $ sudo reboot
```
Verify SPI
```bash
admin@TeamA-1:~ $ ls /dev/spidev*
```
You should see something like this: `/dev/spidev0.0 /dev/spidev0.1`

## Enable the communication with the nRF24 module
First, it is necessary to activate the SPI pins as explained earlier.

Then, install the library by running the following commands.

```bash
sudo apt-get install python3-dev libboost-python-dev python3-setuptools python3-rpi.gpio

git clone https://github.com/nRF24/RF24 nrf24

cd nrf24

./configure --driver=SPIDEV

make

sudo make install

cd pyRF24/
```
The next steps tend to get bugged; who knows why?
```bash
python3 setup.py build
sudo python setup.py install
```
In case it gets bugged, I did this, but I'm not sure if it's necessary for it to work, so try skipping the installation of these libraries and try to do the next steps first.
```bash
sudo apt-get install libboost-all-dev
sudo apt-get install libssl-dev
```
I think the problem is that the Raspberry Pi is running out of memory during the build process, which may cause the compiler to hang. You can temporarily increase the swap space by following these steps:
```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
```
Change the CONF_SWAPSIZE value to a higher number (e.g., 2048 for 2GB). Save the file, and then run:
```bash
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```
----
Now, everything should work. We tested it by running the example from the library. [Example](https://github.com/nRF24/RF24/blob/master/examples_linux/getting_started.py)

## Task: LCD display
For the use of the Python libraries required by the LCD, it is necessary to create a Python environment. To do that, create an environment with the following command:
```bash
python -m venv venv
```
To activate the environment, use:
```bash
source venv/bin/activate
```
Having the Python environment activated can cause problems in finding the nRF24 library. This can be resolved by specifying the library's installation path as follows
```python
import sys
sys.path.append('/usr/local/lib/python3.11/dist-packages/RF24-1.4.10-py3.11-linux-aarch64.egg')
from RF24 import *
```

## Task: Automatic start python code
```bash
sudo nano /etc/systemd/system/mtp.service
```

```python
[Unit]
Description=My Python Script

[Service]
Type=simple
User=admin
WorkingDirectory=/home/admin/main/
ExecStart=/bin/bash -c 'source /home/admin/myenv/bin/activate && exec python3 main.py'
StandardOutput=inherit
StandardError=inherit
Restart=always

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl daemon-reload
sudo systemctl enable mtp.service
sudo systemctl start mtp.service
sudo systemctl status mtp.service
```
To stop the service
```bash
sudo systemctl stop mtp.service
```
