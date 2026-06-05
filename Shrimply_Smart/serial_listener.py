#!/usr/bin/env python3
"""
Serial Listener for Shrimply Smart
Reads sensor data from Arduino over USB Serial
and saves to Django REST API directly (no PHP middleman).
Auto-reconnects on serial disconnect.
"""

import serial
import requests
import time
import sys
import os

# Configuration — route to Django device endpoint
SERIAL_PORT = "COM3"  # Change to your Wemos COM port (check Device Manager)
BAUD_RATE = 115200
DJANGO_ENDPOINT = os.environ.get(
    "DJANGO_URL",
    "http://localhost:8000/api/device/readings/"
)
DEVICE_ID = os.environ.get("DEVICE_ID", "fishpond-01")
DEVICE_TOKEN = os.environ.get(
    "DEVICE_TOKEN",
    "cuXuqJvqQRevJTbejj6Iuf-dIKulTj18o4lkMAeuvVI"
)
RECONNECT_DELAY = 3  # seconds

# Sensor validation ranges
VALID_RANGES = {
    "temperature": (-10, 50),
    "ph":          (0, 14),
    "tds":         (0, 5000),
    "turbidity":   (0, 10),
}

def find_serial_port():
    """Auto-detect Wemos COM port"""
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if 'CH340' in port.description or 'USB' in port.description:
            return port.device
    return None

def validate_reading(temp, ph, tds, turbidity):
    """Validate sensor values are within physically possible ranges."""
    try:
        t = float(temp)
        p = float(ph)
        d = int(float(tds))
        turb = float(turbidity)
    except (ValueError, TypeError) as e:
        return None, f"Non-numeric value: {e}"

    for name, val, (lo, hi) in [
        ("temperature", t, VALID_RANGES["temperature"]),
        ("ph", p, VALID_RANGES["ph"]),
        ("tds", d, VALID_RANGES["tds"]),
        ("turbidity", turb, VALID_RANGES["turbidity"]),
    ]:
        if val < lo or val > hi:
            return None, f"{name} = {val} out of range [{lo}, {hi}]"

    return {"temperature": t, "ph": p, "tds": d, "turbidity": turb}, None

def save_to_database(temp, ph, tds, turbidity):
    """Validate then send sensor data to Django API"""
    data, err = validate_reading(temp, ph, tds, turbidity)
    if err:
        print(f"  ✗ Validation failed: {err}")
        return False

    try:
        print(f"  → Saving: {data}")
        response = requests.post(
            DJANGO_ENDPOINT,
            json=data,
            headers={
                "Content-Type": "application/json",
                "X-Device-Id": DEVICE_ID,
                "X-Device-Token": DEVICE_TOKEN,
            },
            timeout=5,
        )
        if response.status_code == 201:
            print(f"  ✓ Saved OK")
            return True
        else:
            print(f"  ✗ Error {response.status_code}: {response.text}")
            return False
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

def listen_once(port):
    """Open serial port, listen until disconnect. Returns when port closes."""
    print(f"Connecting to {port} at {BAUD_RATE} baud...")
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=1)
        time.sleep(2)  # Wait for Arduino to initialize
        print(f"✓ Connected to {port}")
        print("Listening for sensor data...\n")

        while True:
            if ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line.startswith("DATA:"):
                    try:
                        data_str = line[5:]
                        parts = data_str.split(',')
                        if len(parts) == 4:
                            temp, ph, tds, turbidity = parts
                            print(f"[{time.strftime('%H:%M:%S')}] Raw: {data_str}")
                            save_to_database(temp, ph, tds, turbidity)
                    except Exception as e:
                        print(f"  ✗ Parse error: {e}")
                elif line:
                    print(f"  {line}")
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
    except KeyboardInterrupt:
        raise  # Let main() handle clean exit
    finally:
        if 'ser' in locals():
            ser.close()

def main():
    print("=== Shrimply Smart Serial Listener ===")
    print(f"  Endpoint : {DJANGO_ENDPOINT}")
    print(f"  Device   : {DEVICE_ID}")
    print("Press Ctrl+C to stop\n")

    # Infinite reconnect loop
    while True:
        port = find_serial_port() or SERIAL_PORT
        try:
            listen_once(port)
        except KeyboardInterrupt:
            print("\nExiting...")
            sys.exit(0)
        print(f"⏳ Reconnecting in {RECONNECT_DELAY} seconds...\n")
        time.sleep(RECONNECT_DELAY)

if __name__ == "__main__":
    main()
