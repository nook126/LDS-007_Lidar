# LDS-007 Linux LiDAR Radar

Python app for reading an **Ecovacs LDS-007 LiDAR** through a USB-to-UART adapter and displaying a live radar view.

Protocol reference: [Ecovacs-LDS-007](https://github.com/IvoBiesdorf/Ecovacs-LDS-007)

## Hardware

Required:

- Ecovacs LDS-007
- CP2102 USB-to-UART adapter
- Linux computer
- Separate 5V power supply for the LDS-007

### Power Warning

The LDS-007 must be powered from a **separate 5V supply**.

**Do not power the LDS-007 from the CP2102 adapter.**

### UART Wiring

```text
LDS-007   ->   CP2102
TX        ->   RX
RX        ->   TX
GND       ->   GND
```

## Requirements

- Linux
- Python 3
- Tkinter
- PySerial

Install PySerial (if needed):

```bash
python3 -m pip install pyserial
```

Verify dependencies:

```bash
python3 -c "import tkinter, serial; print('Dependencies OK')"
```

## Find the Serial Port

List USB serial devices:

```bash
ls /dev/ttyUSB*
```

Your adapter is usually:

```text
/dev/ttyUSB0
```

Identify the CP2102 in USB device list:

```bash
lsusb
```

Look for `Silicon Labs CP210x USB to UART Bridge`.

## Run the App

```bash
python3 lds007_radar.py
```

Default serial settings:

```text
Baud rate: 115200
Data bits: 8
Parity:    None
Stop bits: 1
Device:    /dev/ttyUSB0
```

If your adapter appears on a different device path, update the serial port in `lds007_radar.py`.

## LiDAR Control Commands

Start command:

```text
startlds$
```

Stop command:

```text
stoplds$
```

The UI sends these when you press **START** and **STOP**.

## Test from Terminal

Start the LiDAR:

```bash
printf 'startlds$' > /dev/ttyUSB0
```

Read binary packets:

```bash
cat /dev/ttyUSB0 | hexdump -C
```

Expected packet prefix:

```text
FA
```

Example stream:

```text
fa eb da 73 ...
fa ec da 73 ...
fa ed da 73 ...
```

## Troubleshooting

### Permission denied for `/dev/ttyUSB0`

```bash
ls -l /dev/ttyUSB0
```

Add your user to the device's group, then log out and back in.

### No serial device appears

```bash
lsusb
```

```bash
dmesg | tail -30
```

You should see the CP210x driver attach to a `ttyUSB` device.

### No LiDAR data

Check the following:

- LDS-007 has a separate 5V power supply
- LDS-007 GND -> CP2102 GND
- LDS-007 TX -> CP2102 RX
- LDS-007 RX -> CP2102 TX
- Correct `/dev/ttyUSB*` device is used
- Serial settings are `115200 8N1`

## Reference

LDS-007 protocol docs:

- https://github.com/IvoBiesdorf/Ecovacs-LDS-007
