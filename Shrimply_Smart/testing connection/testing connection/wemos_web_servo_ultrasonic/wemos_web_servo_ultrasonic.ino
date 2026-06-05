#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <SoftwareSerial.h>

// Wi-Fi
const char* ssid = "YOTC-4F17BE";
const char* pass = "hni574b6";

// Web server
ESP8266WebServer server(80);

// Serial from Arduino (one-way)
// Wiring (MATCHES YOUR PINS):
//   Arduino D2 (RX) <- WeMos D13/SCK (D5 / GPIO14)  [WeMos TX]
//   Arduino D3 (TX) -> WeMos D12/MISO (D6 / GPIO12) [WeMos RX]
//   GND <-> GND
SoftwareSerial link(D6, D5); // RX, TX

// Latest distance string
String lastDistance = "NA";
String lastServo = "OFF";

static void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleepMode(WIFI_NONE_SLEEP);
  WiFi.begin(ssid, pass);
  Serial.print("Connecting to WiFi: ");
  Serial.println(ssid);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print('.');

    // retry every ~20s
    if (millis() - start > 20000) {
      Serial.println();
      Serial.println("WiFi timeout, retrying...");
      start = millis();
      WiFi.disconnect();
      WiFi.begin(ssid, pass);
    }
  }

  Serial.println();
}

static void handleRoot() {
  String html =
    "<!doctype html><html><head><meta charset='utf-8'/>"
    "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
    "<title>Shrimp Control</title></head><body>"
    "<h2>Servo</h2>"
    "<p><a href='/on'><button style='width:120px;height:40px'>ON</button></a> "
    "<a href='/off'><button style='width:120px;height:40px'>OFF</button></a></p>"
    "<p>Servo state: <span id='s'>...</span></p>"
    "<h2>Ultrasonic</h2>"
    "<p>Distance (cm): <span id='d'>...</span></p>"
    "<script>\n"
    "async function refresh(){\n"
    "  try{\n"
    "    const r = await fetch('/distance');\n"
    "    document.getElementById('d').textContent = await r.text();\n"
    "    const s = await fetch('/servo');\n"
    "    document.getElementById('s').textContent = await s.text();\n"
    "  }catch(e){\n"
    "    document.getElementById('d').textContent = 'ERR';\n"
    "    document.getElementById('s').textContent = 'ERR';\n"
    "  }\n"
    "}\n"
    "refresh(); setInterval(refresh, 6000);\n"
    "</script>"
    "</body></html>";

  server.send(200, "text/html", html);
}

static void handleOn() {
  link.println("S=ON");
  lastServo = "ON";
  server.sendHeader("Location", "/");
  server.send(302, "text/plain", "OK");
}

static void handleOff() {
  link.println("S=OFF");
  lastServo = "OFF";
  server.sendHeader("Location", "/");
  server.send(302, "text/plain", "OK");
}

static void handleDistance() {
  server.send(200, "text/plain", lastDistance);
}

static void handleServo() {
  server.send(200, "text/plain", lastServo);
}

static void readArduinoLines() {
  while (link.available()) {
    String line = link.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) continue;

    // Expect: D=12.3  or D=NA
    if (line.startsWith("D=")) {
      String v = line.substring(2);
      v.trim();
      lastDistance = v;

      Serial.print("Distance: ");
      Serial.println(lastDistance);
    } else if (line.startsWith("ACK=")) {
      // Optional ACK from Arduino: ACK=ON / ACK=OFF
      String v = line.substring(4);
      v.trim();
      if (v.length() > 0) lastServo = v;
      Serial.print("Servo ACK: ");
      Serial.println(lastServo);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(600);

  Serial.println();
  Serial.println("WEMOS BOOT");
  Serial.println("Serial Monitor must be 115200");
  Serial.print("Reset reason: ");
  Serial.println(ESP.getResetReason());

  // Stabilize SoftwareSerial RX
  pinMode(D6, INPUT_PULLUP);

  link.begin(9600);
  link.setTimeout(30);

  connectWiFi();

  Serial.print("WeMos IP: ");
  Serial.println(WiFi.localIP());

  server.on("/", handleRoot);
  server.on("/on", handleOn);
  server.on("/off", handleOff);
  server.on("/distance", handleDistance);
  server.on("/servo", handleServo);
  server.begin();

  Serial.println("Open the IP in either laptop browser.");
  Serial.println("If you see constant trash/reboots: disconnect servo power and power WeMos from a stable USB, then retry.");
}

void loop() {
  server.handleClient();
  readArduinoLines();
}
