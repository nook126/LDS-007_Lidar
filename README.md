# LDS-007 Linux LiDAR Radar

A simple Python application for reading an **Ecovacs LDS-007 LiDAR** through a USB-to-UART adapter and displaying the scan as a live radar.

The project is based on the reverse-engineered protocol from the [Ecovacs-LDS-007](https://github.com/IvoBiesdorf/Ecovacs-LDS-007) project.

## Hardware

You need:

- Ecovacs LDS-007
- CP2102 USB-to-UART adapter
- Linux computer
- Separate 5V power supply for the LDS-007

### Power

The LDS-007 must be powered from a **separate 5V supply**.

**Do not power the LDS-007 through the CP2102.**

The CP2102 is used only for UART communication.

### UART Wiring

```text
LDS-007       CP2102
-------       ------
TX       →    RX
RX       ←    TX
GND      ─    GND


 ## Requirements

- Linux
- Python 3
- Tkinter
- PySerial

 Install Python and the required packages using your Linux distribution's package manager.

 PySerial can also be installed with:

```
python3 -m pip install pyserial
```

 Verify the dependencies:

```
python3 -c "import tkinter, serial; print('Dependencies OK')"
```

 ## Find the Serial Port

 Connect the CP2102 to the computer and check the available serial devices:

```
ls /dev/ttyUSB*
```

 The CP2102 will typically appear as:

```
/dev/ttyUSB0
```

 You can identify the adapter with:

```
lsusb
```

 Look for a Silicon Labs CP210x USB-to-UART device.

 ## Running

 Run the application with:

```
python3 lds007_radar.py
```

 The program communicates with the LDS-007 using:

```
Baud rate: 115200
Data bits: 8
Parity:    None
Stop bits: 1
```

 The default serial device is:

```
/dev/ttyUSB0
```

 If your CP2102 appears as a different device, change the serial port in the Python program.

 ## Controls

 The radar window provides controls for starting and stopping the LiDAR.

 ### Start

 The LDS-007 start command is:

```
startlds$
```

 ### Stop

 The LDS-007 stop command is:

```
stoplds$
```

 The application sends these commands when the **START** and **STOP** buttons are pressed.

 ## Testing the Connection

 You can test the LiDAR directly from the Linux terminal.

 Send the start command:

```
printf 'startlds$' > /dev/ttyUSB0
```

 Then read the binary data:

```
cat /dev/ttyUSB0 | hexdump -C
```

 The LDS-007 data stream should contain packets beginning with:

```
FA
```

 For example:

```
fa eb da 73 ...
fa ec da 73 ...
fa ed da 73 ...
```

 ## Troubleshooting

 ### Permission Denied

 If you cannot access `/dev/ttyUSB0`, check its permissions:

```
ls -l /dev/ttyUSB0
```

 The serial device will belong to a particular Linux group. Add your user to that group if necessary, then log out and back in.

 ### No Serial Device

 Check that the CP2102 is detected:

```
lsusb
```

 Then check the kernel messages:

```
dmesg | tail -30
```

 You should see the CP210x driver being attached to a `ttyUSB` device.

 ### No LiDAR Data

 Check:

 - The LDS-007 has a **separate 5V power supply**
- LDS-007 GND is connected to CP2102 GND
- LDS-007 TX is connected to CP2102 RX
- LDS-007 RX is connected to CP2102 TX
- The correct `/dev/ttyUSB*` device is being used
- The serial configuration is `115200 8N1`

 ### TX/RX Wiring

 The correct connection is:

```
LDS-007 TX  →  CP2102 RX
LDS-007 RX  →  CP2102 TX
LDS-007 GND →  CP2102 GND
```

 Do not connect TX to TX or RX to RX.

 ## Reference

 LDS-007 protocol reference:

 https://github.com/IvoBiesdorf/Ecovacs-LDS-007

```

```
