#include <SoftwareSerial.h>
#include <Servo.h>

// Arduino -> WeMos one-way serial
// Wiring (MATCHES YOUR PINS):
//   Arduino RX D2  <- WeMos D13/SCK (D5 / GPIO14)
//   Arduino TX D3  -> WeMos D12/MISO (D6 / GPIO12)  (LEVEL SHIFT REQUIRED if Arduino is 5V)
//   Arduino GND    <-> WeMos GND
SoftwareSerial linkSerial(2, 3); // RX, TX

// Servo on Arduino
static const uint8_t SERVO_PIN = 9;
static const int SERVO_OFF_ANGLE = 0;
static const int SERVO_ON_ANGLE = 90;
static bool servoOn = false;
static Servo servo;

// Ultrasonic pins
const int trigPin = 5;
const int echoPin = 6;

static float readDistanceCm() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  // 30ms timeout ~5m max (safety)
  unsigned long duration = pulseIn(echoPin, HIGH, 30000);
  if (duration == 0) return -1.0f;

  return (float)duration * 0.034f / 2.0f;
}

void setup() {
  Serial.begin(9600);

  // Stabilize SoftwareSerial RX line
  pinMode(2, INPUT_PULLUP);

  linkSerial.begin(9600);

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);

  Serial.println(F("ARDUINO READY"));
  Serial.println(F("Sending D=<cm> to WeMos every 6s"));
  Serial.println(F("Accepting servo commands: S=ON / S=OFF"));
}

static void applyServoState(bool on) {
  servoOn = on;

  // Attach only while moving to reduce interrupt load (improves SoftwareSerial reliability)
  servo.attach(SERVO_PIN);
  servo.write(servoOn ? SERVO_ON_ANGLE : SERVO_OFF_ANGLE);
  delay(500);
  servo.detach();
}

static void readCommands() {
  while (linkSerial.available()) {
    String cmd = linkSerial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() == 0) continue;

    if (cmd == "S=ON") {
      applyServoState(true);
      Serial.println(F("Servo: ON"));
      linkSerial.println("ACK=ON");
    } else if (cmd == "S=OFF") {
      applyServoState(false);
      Serial.println(F("Servo: OFF"));
      linkSerial.println("ACK=OFF");
    }
  }
}

void loop() {
  readCommands();

  float d = readDistanceCm();

  // Line format:
  //   D=12.3,S=ON\n
  linkSerial.print("D=");
  if (d < 0) linkSerial.print("NA");
  else linkSerial.print(d, 1);
  linkSerial.print(",S=");
  linkSerial.println(servoOn ? "ON" : "OFF");

  Serial.print(F("Distance(cm): "));
  if (d < 0) Serial.println(F("NA"));
  else Serial.println(d, 1);
  Serial.print(F("Servo: "));
  Serial.println(servoOn ? F("ON") : F("OFF"));

  // Keep loop responsive for commands while still sending every 6 seconds
  unsigned long start = millis();
  while (millis() - start < 6000) {
    readCommands();
    delay(5);
  }
}
