<?php
// insert_reading.php
// Inserts a single feeder reading into MySQL.
// This version writes to your EXISTING Django table:
//   DB:    shrimply_smart
//   Table: api_feedinglog
// It fills required fields with safe defaults so inserts succeed.
//
// Accepts POST or GET (preferred names):
//   - servo_state OR servoOnOrOff = ON|OFF (or 1|0)
//   - distance_cm OR distance     = number or NA
//   - api_key                    = optional
//
// NOTE: This endpoint is used by the WeMos sketch, which posts:
//   distance_cm=<value>&servo_state=<ON|OFF>&api_key=<key>

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, GET, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
  http_response_code(204);
  exit;
}

// --- CONFIG ---
// If the repo lives under your WAMP web root (like C:\wamp64\www\Shrimply_Smart\...),
// you can reuse the existing config.php here. If not found, we fall back to defaults.
$maybeFishpondCfg = __DIR__ . '/../../../Fishpond_Water_Monitoring/config.php';
if (file_exists($maybeFishpondCfg)) {
  require_once $maybeFishpondCfg;
}

$DB_HOST = defined('DB_HOST') ? DB_HOST : 'localhost';
$DB_USER = defined('DB_USER') ? DB_USER : 'root';
$DB_PASS = defined('DB_PASS') ? DB_PASS : '';
$DB_NAME = defined('DB_NAME') ? DB_NAME : 'shrimply_smart';

// Table created by schema.sql in this folder.

$TABLE = 'api_feedinglog';

// Column names.
$COL_SERVO = 'servoOnOrOff';
$COL_DIST  = 'distance';

// Optional: set to '' to disable key checking.
$API_KEY = 'shrimp-key-123';

function fail($code, $msg, $extra = []) {
  http_response_code($code);
  echo json_encode(array_merge(['ok' => false, 'error' => $msg], $extra));
  exit;
}

$apiKey = $_REQUEST['api_key'] ?? '';
if ($API_KEY !== '' && $apiKey !== $API_KEY) {
  fail(401, 'bad api_key');
}

$servoRaw = $_REQUEST['servo_state'] ?? ($_REQUEST['servoOnOrOff'] ?? ($_REQUEST['servoOnOff'] ?? ($_REQUEST['servo'] ?? '')));
$servo = strtoupper(trim((string)$servoRaw));
if ($servo === '1') $servo = 'ON';
if ($servo === '0') $servo = 'OFF';
if ($servo !== 'ON' && $servo !== 'OFF') {
  fail(400, 'servo_state (or servoOnOrOff) must be ON or OFF');
}

$distanceRaw = trim((string)($_REQUEST['distance_cm'] ?? ($_REQUEST['distance'] ?? '')));
$distance = null;
if ($distanceRaw === '' || strtoupper($distanceRaw) === 'NA') {
  $distance = null;
} else {
  if (!is_numeric($distanceRaw)) {
    fail(400, 'distance_cm (or distance) must be numeric or NA');
  }
  $distance = floatval($distanceRaw);
}

$mysqli = new mysqli($DB_HOST, $DB_USER, $DB_PASS, $DB_NAME);
if ($mysqli->connect_error) {
  fail(500, 'db connect failed');
}

// Resolve feeder_id (required by api_feedinglog foreign key)
$feederIdRaw = $_REQUEST['feeder_id'] ?? '';
$feederId = null;
if ($feederIdRaw !== '' && ctype_digit((string)$feederIdRaw)) {
  $feederId = intval($feederIdRaw);
} else {
  $r = $mysqli->query('SELECT MIN(`id`) AS id FROM `api_feeder`');
  if ($r) {
    $row = $r->fetch_assoc();
    $r->free();
    if ($row && $row['id'] !== null) $feederId = intval($row['id']);
  }
}

if ($feederId === null || $feederId <= 0) {
  $mysqli->close();
  fail(500, 'no feeder_id available (api_feeder is empty)');
}

// Required fields in api_feedinglog
$feedType = $_REQUEST['feed_type'] ?? 'manual';
$portion = isset($_REQUEST['portion_grams']) && is_numeric($_REQUEST['portion_grams']) ? intval($_REQUEST['portion_grams']) : 0;
$capBefore = isset($_REQUEST['capacity_before']) && is_numeric($_REQUEST['capacity_before']) ? intval($_REQUEST['capacity_before']) : 0;
$capAfter  = isset($_REQUEST['capacity_after']) && is_numeric($_REQUEST['capacity_after']) ? intval($_REQUEST['capacity_after']) : $capBefore;
$notes = (string)($_REQUEST['notes'] ?? '');

// Insert
if ($distance === null) {
  $sql = 'INSERT INTO `'.$TABLE.'` (`timestamp`,`feed_type`,`portion_grams`,`capacity_before`,`capacity_after`,`weather_conditions`,`notes`,`feeder_id`,`'.$COL_SERVO.'`,`'.$COL_DIST.'`) '
       . 'VALUES (NOW(6), ?, ?, ?, ?, NULL, ?, ?, ?, NULL)';
  $stmt = $mysqli->prepare($sql);
  if (!$stmt) {
    $mysqli->close();
    fail(500, 'prepare failed');
  }
  $stmt->bind_param('siiisis', $feedType, $portion, $capBefore, $capAfter, $notes, $feederId, $servo);
} else {
  $sql = 'INSERT INTO `'.$TABLE.'` (`timestamp`,`feed_type`,`portion_grams`,`capacity_before`,`capacity_after`,`weather_conditions`,`notes`,`feeder_id`,`'.$COL_SERVO.'`,`'.$COL_DIST.'`) '
       . 'VALUES (NOW(6), ?, ?, ?, ?, NULL, ?, ?, ?, ?)';
  $stmt = $mysqli->prepare($sql);
  if (!$stmt) {
    $mysqli->close();
    fail(500, 'prepare failed');
  }
  $stmt->bind_param('siiisisd', $feedType, $portion, $capBefore, $capAfter, $notes, $feederId, $servo, $distance);
}

if (!$stmt->execute()) {
  $err = $stmt->error;
  $stmt->close();
  $mysqli->close();
  fail(500, 'execute failed', ['detail' => $err]);
}

$id = $stmt->insert_id;
$stmt->close();

$mysqli->close();

echo json_encode([
  'ok' => true,
  'id' => $id,
  'servoOnOrOff' => $servo,
  'distance' => $distance,
  'feeder_id' => $feederId,
  'db' => $DB_NAME,
  'table' => $TABLE,
]);
