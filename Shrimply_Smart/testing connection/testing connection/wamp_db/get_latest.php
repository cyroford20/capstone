<?php
// get_latest.php

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');

// Reuse Fishpond_Water_Monitoring/config.php if available.
$maybeFishpondCfg = __DIR__ . '/../../../Fishpond_Water_Monitoring/config.php';
if (file_exists($maybeFishpondCfg)) {
  require_once $maybeFishpondCfg;
}

$DB_HOST = defined('DB_HOST') ? DB_HOST : 'localhost';
$DB_USER = defined('DB_USER') ? DB_USER : 'root';
$DB_PASS = defined('DB_PASS') ? DB_PASS : '';
$DB_NAME = defined('DB_NAME') ? DB_NAME : 'shrimply_smart';
$TABLE   = 'api_feedinglog';

// Column names.
$COL_ID    = 'id';
$COL_TS    = 'timestamp';
$COL_SERVO = 'servoOnOrOff';
$COL_DIST  = 'distance';

$mysqli = new mysqli($DB_HOST, $DB_USER, $DB_PASS, $DB_NAME);
if ($mysqli->connect_error) {
  http_response_code(500);
  echo json_encode(['ok' => false, 'error' => 'db connect failed']);
  exit;
}

$q = 'SELECT `'.$COL_ID.'` AS id, `'.$COL_TS.'` AS ts, `'.$COL_SERVO.'` AS servoOnOrOff, `'.$COL_DIST.'` AS distance '
   . 'FROM `'.$TABLE.'` ORDER BY `'.$COL_ID.'` DESC LIMIT 1';
$res = $mysqli->query($q);
if (!$res) {
  http_response_code(500);
  echo json_encode([
    'ok' => false,
    'error' => 'query failed',
    'hint' => 'Confirm table/columns exist: api_feedinglog(id,timestamp,servoOnOrOff,distance,feeder_id,...)',
    'db' => $DB_NAME,
    'table' => $TABLE,
  ]);
  exit;
}

$row = $res->fetch_assoc();
$res->free();
$mysqli->close();

if (!$row) {
  echo json_encode(['ok' => true, 'latest' => null]);
  exit;
}

$row['id'] = intval($row['id']);
$row['distance'] = ($row['distance'] === null) ? null : floatval($row['distance']);

echo json_encode(['ok' => true, 'latest' => $row, 'db' => $DB_NAME, 'table' => $TABLE]);
