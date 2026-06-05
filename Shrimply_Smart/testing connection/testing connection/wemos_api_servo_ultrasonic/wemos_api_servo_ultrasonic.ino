#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <SoftwareSerial.h>

// If your Wi-Fi router/hotspot has "client/AP isolation" enabled, devices can't talk to each other.
// Symptom: WeMos shows STA IP (e.g. 192.168.8.44) but laptop can't ping/HTTP it, and WeMos can't reach laptop.
// Workaround: enable SoftAP-only mode and connect the laptop to the WeMos AP (SSID below).
// NOTE: In SoftAP-only mode, set WAMP_HOST to the laptop IP on the WeMos AP network (often 192.168.4.2).
#define USE_SOFTAP_ONLY 0

// Wi-Fi (STA)
const char* ssid = "YOTC-4F17BE";
const char* pass = "hni574b6";

// Fallback AP if STA can't connect
const char* apSsid = "ShrimpWeMos";
const char* apPass = "12345678"; // 8+ chars required

// WAMP (PHP) endpoint to store readings
// If this repo is already inside your WAMP web root (C:\wamp64\www\Shrimply_Smart\...),
// you can post directly to the PHP endpoint within this repo.
// Set WAMP_HOST to your WAMP laptop IP.
const char* WAMP_HOST = "192.168.8.40";
const uint16_t WAMP_PORT = 80;
// Option A (recommended):
//   Put the PHP bridge under your active Apache docroot as:
//     <docroot>/shrimp-db/wamp_db/insert_reading.php
//   Then use:
const char* WAMP_PATH = "/shrimp-db/wamp_db/insert_reading.php";

// Option B (if you serve this repo directly under Apache):
// const char* WAMP_PATH = "/Shrimply_Smart/testing%20connection/testing%20connection/wamp_db/insert_reading.php";

// Must match the PHP file `insert_reading.php`
const char* API_KEY = "shrimp-key-123";

static unsigned long g_lastPostMs = 0;

static IPAddress g_wampIp;

static void printNetInfo() {
    Serial.print("WiFi status: ");
    Serial.println((int)WiFi.status());
    Serial.print("SSID: ");
    Serial.println(WiFi.SSID());
    Serial.print("STA IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("Gateway: ");
    Serial.println(WiFi.gatewayIP());
    Serial.print("Subnet: ");
    Serial.println(WiFi.subnetMask());
}

// Web server (API only)
ESP8266WebServer server(80);

    // Serial link to Arduino (matches your wiring):
    //   Arduino D2 (RX) <- WeMos D13/SCK (D5 / GPIO14)  [WeMos TX]
    //   Arduino D3 (TX) -> WeMos D12/MISO (D6 / GPIO12) [WeMos RX]
    //   GND <-> GND
SoftwareSerial link(D6, D5); // RX, TX

String lastDistance = "NA";
String lastServo = "OFF";

static bool g_wifiOk = false;
static unsigned long g_lastBeatMs = 0;

static void sendCorsHeaders() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.sendHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
    server.sendHeader("Cache-Control", "no-store");
}

static void handleOptions() {
    sendCorsHeaders();
    server.send(204);
}

static void startSoftAp() {
    WiFi.mode(WIFI_AP);
    bool ok = WiFi.softAP(apSsid, apPass);
    Serial.print("SoftAP ");
    Serial.print(ok ? "started" : "failed");
    Serial.print(" SSID=");
    Serial.println(apSsid);
    Serial.print("AP IP: ");
    Serial.println(WiFi.softAPIP());
}

static void connectWiFiOrAp() {
    if (USE_SOFTAP_ONLY) {
        Serial.println("SoftAP-only mode enabled; skipping STA connect.");
        g_wifiOk = false;
        startSoftAp();
        return;
    }

    // Try STA first (connect to your router/hotspot)
    WiFi.mode(WIFI_STA);
    WiFi.setSleepMode(WIFI_NONE_SLEEP);
    WiFi.begin(ssid, pass);

    Serial.print("Connecting to WiFi (STA): ");
    Serial.println(ssid);

    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
        delay(500);
        Serial.print('.');
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        g_wifiOk = true;
        Serial.print("STA IP: ");
        Serial.println(WiFi.localIP());

        if (!g_wampIp.fromString(WAMP_HOST)) {
            Serial.print("WARN: WAMP_HOST is not a valid IP: ");
            Serial.println(WAMP_HOST);
        } else {
            Serial.print("WAMP IP: ");
            Serial.println(g_wampIp);
        }
        printNetInfo();
        return;
    }

    Serial.println("STA connect failed. Starting AP mode...");
    g_wifiOk = false;
    startSoftAp();
}

static void apiDistance() {
    sendCorsHeaders();
    server.send(200, "text/plain", lastDistance);
}

static void apiServoState() {
    sendCorsHeaders();
    server.send(200, "text/plain", lastServo);
}

static void apiServoOn() {
    link.println("S=ON");
    lastServo = "ON";
    sendCorsHeaders();
    server.send(200, "text/plain", "OK");
}

static void apiServoOff() {
    link.println("S=OFF");
    lastServo = "OFF";
    sendCorsHeaders();
    server.send(200, "text/plain", "OK");
}

static void apiPing() {
    sendCorsHeaders();
    server.send(200, "text/plain", "PONG");
}

static void handleRoot() {
    // No embedded UI; just a hint.
    sendCorsHeaders();
    server.send(200, "text/plain",
                            "WeMos API only. Use /api/distance, /api/servo, /api/servo/on, /api/servo/off");
}

static void readArduinoLines() {
    while (link.available()) {
        String line = link.readStringUntil('\n');
        line.trim();
        if (line.length() == 0) continue;

        // Expect: D=12.3,S=ON  (distance can be NA)
        if (line.startsWith("D=")) {
            int comma = line.indexOf(',');
            String dPart = (comma >= 0) ? line.substring(2, comma) : line.substring(2);
            dPart.trim();
            lastDistance = dPart;

            int sIdx = line.indexOf("S=");
            if (sIdx >= 0) {
                String sPart = line.substring(sIdx + 2);
                sPart.trim();
                if (sPart.length() > 0) lastServo = sPart;
            }

            Serial.print("Distance: ");
            Serial.print(lastDistance);
            Serial.print("  Servo: ");
            Serial.println(lastServo);

            // Post to WAMP at most once per 6 seconds
            unsigned long now = millis();
            if (now - g_lastPostMs >= 5500) {
                g_lastPostMs = now;

                bool netOk = (WiFi.status() == WL_CONNECTED) || (WiFi.getMode() & WIFI_AP);
                if (netOk) {
                    WiFiClient client;
                    client.setTimeout(2000);

                    HTTPClient http;
                    http.setTimeout(2000);

                    String url = String("http://") + WAMP_HOST + ":" + String(WAMP_PORT) + WAMP_PATH;
                    Serial.print("WAMP URL: ");
                    Serial.println(url);

                    // Quick connectivity check (helps diagnose HTTP -1)
                    Serial.print("WAMP TCP connect: ");
                    bool tcpOk = false;
                    if (g_wampIp) {
                        tcpOk = client.connect(g_wampIp, WAMP_PORT);
                    } else {
                        tcpOk = client.connect(WAMP_HOST, WAMP_PORT);
                    }
                    if (tcpOk) {
                        Serial.println("OK");
                        client.stop();
                    } else {
                        Serial.println("FAIL");
                        printNetInfo();
                    }

                    // ESP8266HTTPClient (core 3.1.2) does NOT have begin(WiFiClient&, IPAddress,...)
                    // Use the supported overload: begin(client, hostString, port, uri)
                    bool beginOk = http.begin(client, String(WAMP_HOST), WAMP_PORT, String(WAMP_PATH));

                    if (beginOk) {
                        http.addHeader("Content-Type", "application/x-www-form-urlencoded");

                        String body = String("api_key=") + API_KEY +
                                      "&distance_cm=" + lastDistance +
                                      "&servo_state=" + lastServo;

                        int code = http.POST(body);
                        Serial.print("WAMP POST => HTTP ");
                        Serial.println(code);

                        if (code <= 0) {
                            Serial.print("WAMP ERROR: ");
                            Serial.println(http.errorToString(code));
                        }

                        String resp = http.getString();
                        Serial.print("WAMP RESP: ");
                        Serial.println(resp);
                        http.end();
                    } else {
                        Serial.println("WAMP POST begin() failed");
                    }
                } else {
                    Serial.println("WiFi not connected; skip WAMP POST");
                }
            }
        } else if (line.startsWith("ACK=")) {
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
    delay(1200); // give Serial Monitor time to attach

    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, HIGH); // off (active-low)

    Serial.println();
    Serial.println("WEMOS API BOOT");
    Serial.println("Serial Monitor must be 115200");
    Serial.print("Reset reason: ");
    Serial.println(ESP.getResetReason());

    // Stabilize SoftwareSerial RX
    pinMode(D6, INPUT_PULLUP);

    link.begin(9600);
    link.setTimeout(30);

    connectWiFiOrAp();

    Serial.println("Endpoints:");
    Serial.println(" - /api/ping");
    Serial.println(" - /api/distance");
    Serial.println(" - /api/servo");
    Serial.println(" - /api/servo/on");
    Serial.println(" - /api/servo/off");

    server.on("/", handleRoot);

    server.on("/api/ping", HTTP_OPTIONS, handleOptions);
    server.on("/api/ping", HTTP_GET, apiPing);

    server.on("/api/distance", HTTP_OPTIONS, handleOptions);
    server.on("/api/distance", HTTP_GET, apiDistance);

    server.on("/api/servo", HTTP_OPTIONS, handleOptions);
    server.on("/api/servo", HTTP_GET, apiServoState);

    server.on("/api/servo/on", HTTP_OPTIONS, handleOptions);
    server.on("/api/servo/on", HTTP_GET, apiServoOn);

    server.on("/api/servo/off", HTTP_OPTIONS, handleOptions);
    server.on("/api/servo/off", HTTP_GET, apiServoOff);

    server.begin();
    Serial.println("API ready.");
}

void loop() {
    // Recover if WiFi drops (common on some routers/hotspots)
    if (g_wifiOk && WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi dropped; reconnecting...");
        connectWiFiOrAp();
    }

    server.handleClient();
    readArduinoLines();

    // heartbeat LED (blinks ~1Hz) so you know the sketch is running
    unsigned long now = millis();
    if (now - g_lastBeatMs >= 500) {
        g_lastBeatMs = now;
        digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    }
}
