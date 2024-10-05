# MTP-TeamA (The Winning Team)

## Summary table
- **Microcontroller**: Raspberry Pi Zero 2 W
- **Operating System**: Raspberry Pi OS Lite (Terminal Only)
- **Transciever**: nRF24L01
- **Programming language**: C++

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

## Tasks
- [x] Install OS & Set up.
- [ ] Read file from USB: Detect when an USB device has been connected and read the content of the .txt file.
- [ ] Ping with the tranciever: Enable the communication with the nRF24 module.

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
## Enabling SPI bus
```bash
admin@TeamA-1:~ $ sudo raspi-config
```
Navigate to the Interfacing Options menu:

Use the arrow keys to navigate to the option labeled Interfacing Options and press Enter.

Select SPI:

In the Interfacing Options menu, select the option SPI (Serial Peripheral Interface) and press Enter.

Enable SPI:

When prompted to enable the SPI interface, select Yes.

Reboot
```bash
admin@TeamA-1:~ $ sudo reboot
```
Verify SPI
```bash
admin@TeamA-1:~ $ ls /dev/spidev*
```
You should see something like this: `/dev/spidev0.0 /dev/spidev0.1`




