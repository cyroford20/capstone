# testing connection

This folder contains two simple sketches:

- `arduino_ultrasonic_tx_6s/arduino_ultrasonic_tx_6s.ino`
  - Reads ultrasonic distance on Arduino and sends it every **6 seconds** over SoftwareSerial.
  - Sends lines like: `D=12.3` or `D=NA`.

- `wemos_web_servo_ultrasonic/wemos_web_servo_ultrasonic.ino`
  - (Old) WeMos-hosted web page + Arduino link.

- `wemos_api_servo_ultrasonic/wemos_api_servo_ultrasonic.ino`
  - (Recommended) WeMos exposes an API only (no embedded web UI):
    - `GET /api/distance`
    - `GET /api/servo`
    - `GET /api/servo/on`
    - `GET /api/servo/off`
  - ALSO posts each new reading to WAMP/MySQL (see `wamp_db/`).

- `web_ui/index.html`
  - Separate web page (runs on your laptop/WAMP) that calls the WeMos API.

- `wamp_db/`
  - PHP + SQL files for WAMP + MySQL.
  - WeMos will POST readings to `insert_reading.php`.
  - Web can display latest data from MySQL using `dashboard.html`.

## Wiring

### Arduino -> WeMos (serial)
- Arduino **D2 (RX)** <- WeMos **D13/SCK (D5 / GPIO14)**
- Arduino **D3 (TX)** -> WeMos **D12/MISO (D6 / GPIO12)** **through a voltage divider / level shifter**
- Arduino **GND** <-> WeMos **GND** (common ground)

### Ultrasonic (Arduino)
- trig = D5
- echo = D6

### Servo (Arduino)
- servo signal = Arduino **D9**
- servo power = external **5V** supply (recommended)
- servo GND must connect to Arduino GND (common ground)

## Use
1. Upload the Arduino sketch to the Arduino.
2. Upload the WeMos API sketch to the WeMos: `wemos_api_servo_ultrasonic/wemos_api_servo_ultrasonic.ino`.
3. Open Serial Monitor for WeMos at **115200** and copy the IP address.
4. Edit `web_ui/index.html` and set `WEMOS_BASE` to `http://<WEMOS_IP>`.
5. Host `web_ui/` on your laptop (WAMP): copy it into `C:\wamp64\www\shrimp-ui\`.
6. Open the page from either laptop:
  - On WAMP laptop: `http://localhost/shrimp-ui/`
  - From the other laptop (same Wi-Fi): `http://<WAMP_LAPTOP_IP>/shrimp-ui/`
