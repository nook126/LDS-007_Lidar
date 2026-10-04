
#!/usr/bin/env python3

import serial
import threading
import time
import math
import tkinter as tk
from tkinter import ttk, messagebox


# ============================================================
# Configuration
# ============================================================

SERIAL_PORT = "/dev/ttyUSB0"
BAUDRATE = 115200

PACKET_SIZE = 22
HEADER = 0xFA

START_COMMAND = b"startlds$"
STOP_COMMAND = b"stoplds$"

# Radar display
WINDOW_SIZE = 800

# Maximum displayed distance in mm.
# Change this to 3000 for a 3 meter radar, for example.
MAX_DISTANCE_MM = 3000

# The Arduino project uses d / 15 for its display scaling.
# We instead dynamically scale to MAX_DISTANCE_MM.
MIN_DISTANCE_MM = 50


# ============================================================
# LDS-007 decoder
# ============================================================

class LDS007:
    def __init__(self, port):
        self.port_name = port
        self.serial = None

        self.running = False
        self.thread = None

        self.lock = threading.Lock()

        # 360 degrees of data
        self.distances = [0] * 360
        self.intensities = [0] * 360
        self.received = [False] * 360

        self.packet_count = 0
        self.valid_packet_count = 0

        self.last_index = None

        self.status_callback = None

    def set_status_callback(self, callback):
        self.status_callback = callback

    def status(self, text):
        print(text)

        if self.status_callback:
            self.status_callback(text)

    def connect(self):
        self.serial = serial.Serial(
            self.port_name,
            BAUDRATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1
        )

        # Give the device a moment after opening the UART
        time.sleep(0.2)

        self.status(
            f"Connected to {self.port_name} @ {BAUDRATE} 8N1"
        )

    def send_start(self):
        if not self.serial:
            return

        self.serial.write(START_COMMAND)
        self.serial.flush()

        self.status("Sent: startlds$")

    def send_stop(self):
        if not self.serial:
            return

        self.serial.write(STOP_COMMAND)
        self.serial.flush()

        self.status("Sent: stoplds$")

    def start(self):
        if self.running:
            return

        try:
            if self.serial is None or not self.serial.is_open:
                self.connect()

            # Same command used by the Arduino repository
            self.send_start()

            self.running = True

            self.thread = threading.Thread(
                target=self.read_loop,
                daemon=True
            )

            self.thread.start()

        except Exception as e:
            self.status(f"ERROR: {e}")
            raise

    def stop(self):
        self.running = False

        try:
            self.send_stop()
        except Exception:
            pass

    def close(self):
        self.running = False

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass

        self.serial = None

    def read_exact(self, count):
        data = bytearray()

        deadline = time.monotonic() + 0.1

        while len(data) < count and self.running:
            if time.monotonic() > deadline:
                return None

            chunk = self.serial.read(count - len(data))

            if chunk:
                data.extend(chunk)

        if len(data) != count:
            return None

        return bytes(data)

    def read_loop(self):
        self.status("Reading LDS-007 data...")

        while self.running:

            try:
                # ------------------------------------------------
                # Find 0xFA packet header
                # ------------------------------------------------

                b = self.serial.read(1)

                if not b:
                    continue

                if b[0] != HEADER:
                    continue

                # ------------------------------------------------
                # We already consumed FA.
                # Read remaining 21 bytes.
                # ------------------------------------------------

                rest = self.read_exact(PACKET_SIZE - 1)

                if rest is None:
                    continue

                packet = bytes([HEADER]) + rest

                self.packet_count += 1

                # ------------------------------------------------
                # Decode packet
                # ------------------------------------------------

                self.decode_packet(packet)

            except serial.SerialException as e:
                self.status(f"Serial error: {e}")
                break

            except Exception as e:
                self.status(f"Decoder error: {e}")

        self.status("Reader stopped.")

    def decode_packet(self, pkt):

        if len(pkt) != 22:
            return

        # --------------------------------------------------------
        # Packet format from the LDS-007 Arduino implementation:
        #
        # pkt[0]       = FA
        # pkt[1]       = packet index
        #
        # pkt[4..19]   = four measurements
        #
        # pkt[20..21]  = checksum
        # --------------------------------------------------------

        idx = pkt[1]

        # The repository uses:
        #
        # block = idx - 0xA0
        #
        # angle = block * 4 + measurement number
        #
        if idx < 0xA0 or idx > 0xF9:
            return

        block = idx - 0xA0

        self.last_index = idx

        # Four measurements per packet
        for i in range(4):

            base = 4 + i * 4

            # LDS-007 distance
            distance = (
                pkt[base]
                | ((pkt[base + 1] & 0x3F) << 8)
            )

            # LDS-007 intensity
            intensity = (
                pkt[base + 2]
                | (pkt[base + 3] << 8)
            )

            angle = block * 4 + i

            if 0 <= angle < 360:

                with self.lock:
                    self.distances[angle] = distance
                    self.intensities[angle] = intensity
                    self.received[angle] = True

        self.valid_packet_count += 1

    def get_scan(self):
        with self.lock:
            return (
                self.distances[:],
                self.intensities[:],
                self.received[:],
                self.packet_count,
                self.valid_packet_count,
                self.last_index
            )


# ============================================================
# Radar GUI
# ============================================================

class RadarApp:

    def __init__(self, root):

        self.root = root
        self.root.title("Ecovacs LDS-007 LiDAR Radar")

        self.root.configure(bg="#101010")

        self.lidar = LDS007(SERIAL_PORT)
        self.lidar.set_status_callback(self.serial_status)

        self.running = False

        self.points = []

        self.build_ui()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close
        )

        # Start GUI update loop
        self.update_radar()

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def build_ui(self):

        top = tk.Frame(
            self.root,
            bg="#101010"
        )

        top.pack(
            fill=tk.X,
            padx=10,
            pady=8
        )

        title = tk.Label(
            top,
            text="LDS-007 LiDAR RADAR",
            font=("Arial", 20, "bold"),
            fg="#00ff66",
            bg="#101010"
        )

        title.pack(side=tk.LEFT)

        self.status_label = tk.Label(
            top,
            text="Disconnected",
            font=("Arial", 11),
            fg="#ff5555",
            bg="#101010"
        )

        self.status_label.pack(
            side=tk.RIGHT,
            padx=10
        )

        # ----------------------------------------------------
        # Radar canvas
        # ----------------------------------------------------

        self.canvas = tk.Canvas(
            self.root,
            width=WINDOW_SIZE,
            height=WINDOW_SIZE,
            bg="#020805",
            highlightthickness=1,
            highlightbackground="#174d2a"
        )

        self.canvas.pack(
            padx=10,
            pady=5
        )

        # ----------------------------------------------------
        # Controls
        # ----------------------------------------------------

        controls = tk.Frame(
            self.root,
            bg="#101010"
        )

        controls.pack(
            fill=tk.X,
            padx=10,
            pady=8
        )

        self.start_button = tk.Button(
            controls,
            text="START",
            command=self.start_lidar,
            width=12,
            bg="#0b6e32",
            fg="white",
            activebackground="#0fa84c"
        )

        self.start_button.pack(
            side=tk.LEFT,
            padx=5
        )

        self.stop_button = tk.Button(
            controls,
            text="STOP",
            command=self.stop_lidar,
            width=12,
            bg="#7a2020",
            fg="white",
            activebackground="#b52c2c"
        )

        self.stop_button.pack(
            side=tk.LEFT,
            padx=5
        )

        self.clear_button = tk.Button(
            controls,
            text="CLEAR",
            command=self.clear_radar,
            width=12,
            bg="#333333",
            fg="white"
        )

        self.clear_button.pack(
            side=tk.LEFT,
            padx=5
        )

        # ----------------------------------------------------
        # Information
        # ----------------------------------------------------

        self.info_label = tk.Label(
            controls,
            text="Packets: 0   Points: 0",
            font=("Courier", 10),
            fg="#00ff66",
            bg="#101010"
        )

        self.info_label.pack(
            side=tk.RIGHT,
            padx=10
        )

    # --------------------------------------------------------
    # Serial status
    # --------------------------------------------------------

    def serial_status(self, text):

        # Called from serial thread.
        # Schedule GUI update on Tk thread.

        self.root.after(
            0,
            lambda: self.status_label.config(
                text=text[:60],
                fg="#00ff66"
            )
        )

    # --------------------------------------------------------
    # Start
    # --------------------------------------------------------

    def start_lidar(self):

        try:

            self.lidar.start()

            self.running = True

            self.status_label.config(
                text="RUNNING",
                fg="#00ff66"
            )

        except Exception as e:

            messagebox.showerror(
                "LDS-007 Error",
                str(e)
            )

            self.status_label.config(
                text="ERROR",
                fg="#ff3333"
            )

    # --------------------------------------------------------
    # Stop
    # --------------------------------------------------------

    def stop_lidar(self):

        self.lidar.stop()

        self.running = False

        self.status_label.config(
            text="STOPPED",
            fg="#ff5555"
        )

    # --------------------------------------------------------
    # Clear
    # --------------------------------------------------------

    def clear_radar(self):

        with self.lidar.lock:

            self.lidar.distances = [0] * 360
            self.lidar.intensities = [0] * 360
            self.lidar.received = [False] * 360

        self.canvas.delete("all")

    # --------------------------------------------------------
    # Draw radar
    # --------------------------------------------------------

    def draw_radar(
        self,
        distances,
        intensities,
        received
    ):

        c = self.canvas

        c.delete("all")

        cx = WINDOW_SIZE / 2
        cy = WINDOW_SIZE / 2

        # Leave some room around the radar
        radar_radius = (WINDOW_SIZE / 2) - 35

        # ----------------------------------------------------
        # Background
        # ----------------------------------------------------

        c.create_oval(
            cx - radar_radius,
            cy - radar_radius,
            cx + radar_radius,
            cy + radar_radius,
            fill="#020805",
            outline="#164d2a"
        )

        # ----------------------------------------------------
        # Distance rings
        # ----------------------------------------------------

        for fraction in (0.25, 0.5, 0.75, 1.0):

            r = radar_radius * fraction

            c.create_oval(
                cx - r,
                cy - r,
                cx + r,
                cy + r,
                outline="#174d2a"
            )

            distance = int(
                MAX_DISTANCE_MM * fraction
            )

            c.create_text(
                cx + 5,
                cy - r + 10,
                text=f"{distance} mm",
                anchor="w",
                fill="#267d45",
                font=("Arial", 8)
            )

        # ----------------------------------------------------
        # Angle lines
        # ----------------------------------------------------

        for angle in range(0, 360, 30):

            rad = math.radians(angle)

            x = cx + math.cos(rad) * radar_radius
            y = cy - math.sin(rad) * radar_radius

            c.create_line(
                cx,
                cy,
                x,
                y,
                fill="#123c24"
            )

            # Labels
            label_x = cx + math.cos(rad) * (radar_radius + 15)
            label_y = cy - math.sin(rad) * (radar_radius + 15)

            label = str(angle)

            c.create_text(
                label_x,
                label_y,
                text=label,
                fill="#28854a",
                font=("Arial", 8)
            )

        # ----------------------------------------------------
        # Crosshair
        # ----------------------------------------------------

        c.create_line(
            cx - radar_radius,
            cy,
            cx + radar_radius,
            cy,
            fill="#0d351e"
        )

        c.create_line(
            cx,
            cy - radar_radius,
            cx,
            cy + radar_radius,
            fill="#0d351e"
        )

        # ----------------------------------------------------
        # LiDAR point cloud
        # ----------------------------------------------------

        point_count = 0

        for angle in range(360):

            if not received[angle]:
                continue

            distance = distances[angle]
            intensity = intensities[angle]

            if distance < MIN_DISTANCE_MM:
                continue

            if distance > MAX_DISTANCE_MM:
                continue

            # Scale distance to radar radius
            r = (
                distance / MAX_DISTANCE_MM
            ) * radar_radius

            # 0 degrees points to the right.
            # Positive angle rotates counter-clockwise.
            rad = math.radians(angle)

            x = cx + math.cos(rad) * r
            y = cy - math.sin(rad) * r

            # ------------------------------------------------
            # Color based on intensity
            # ------------------------------------------------

            # Clamp intensity
            i = min(max(intensity, 0), 1000)

            brightness = int(
                60 + (i / 1000.0) * 195
            )

            brightness = min(
                max(brightness, 60),
                255
            )

            # Green radar color
            color = (
                f"#00{brightness:02x}"
                f"{min(brightness + 30, 255):02x}"
            )

            # Larger point for stronger return
            radius = 2

            if intensity > 500:
                radius = 3

            if intensity > 1000:
                radius = 4

            c.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill=color,
                outline=""
            )

            point_count += 1

        # ----------------------------------------------------
        # LiDAR center
        # ----------------------------------------------------

        c.create_oval(
            cx - 5,
            cy - 5,
            cx + 5,
            cy + 5,
            fill="#00ff66",
            outline=""
        )

        # ----------------------------------------------------
        # Header
        # ----------------------------------------------------

        c.create_text(
            15,
            15,
            text="LDS-007",
            anchor="nw",
            fill="#00ff66",
            font=("Arial", 12, "bold")
        )

        c.create_text(
            15,
            35,
            text=f"Range: {MAX_DISTANCE_MM} mm",
            anchor="nw",
            fill="#267d45",
            font=("Arial", 9)
        )

        return point_count

    # --------------------------------------------------------
    # Update radar
    # --------------------------------------------------------

    def update_radar(self):

        try:

            (
                distances,
                intensities,
                received,
                packet_count,
                valid_packets,
                last_index
            ) = self.lidar.get_scan()

            point_count = self.draw_radar(
                distances,
                intensities,
                received
            )

            self.info_label.config(
                text=(
                    f"Packets: {packet_count}   "
                    f"Valid: {valid_packets}   "
                    f"Points: {point_count}   "
                    f"Index: "
                    f"{last_index if last_index is not None else '--'}"
                )
            )

        except Exception as e:

            print("GUI error:", e)

        # ~30 FPS
        self.root.after(
            33,
            self.update_radar
        )

    # --------------------------------------------------------
    # Close
    # --------------------------------------------------------

    def on_close(self):

        try:
            self.lidar.stop()
        except Exception:
            pass

        try:
            self.lidar.close()
        except Exception:
            pass

        self.root.destroy()


# ============================================================
# Main
# ============================================================

def main():

    print()
    print("======================================")
    print("       LDS-007 Linux Radar")
    print("======================================")
    print()
    print(f"Serial port : {SERIAL_PORT}")
    print(f"Baud rate   : {BAUDRATE}")
    print("Format      : 8N1")
    print()
    print("Starting GUI...")
    print()

    root = tk.Tk()

    app = RadarApp(root)

    root.mainloop()


if __name__ == "__main__":
    main()
