<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

require_once __DIR__ . '/config.php';

$mysqli = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
if ($mysqli->connect_errno) {
    http_response_code(500);
    echo json_encode(['status' => 'error', 'message' => 'DB connection failed']);
    exit;
}

$res = $mysqli->query("SELECT id, timestamp AS ts, temperature, ph, turbidity, tds FROM api_sensorreading ORDER BY timestamp DESC LIMIT 1");
if (!$res) {
    http_response_code(500);
    echo json_encode(['status' => 'error', 'message' => 'Query failed']);
    $mysqli->close();
    exit;
}

$row = $res->fetch_assoc();
$res->free();
$mysqli->close();

if ($row) {
    // Cast to proper types for JSON
    $row['temperature'] = floatval($row['temperature']);
    $row['ph']          = floatval($row['ph']);
    $row['turbidity']      = floatval($row['turbidity']);
    $row['tds']         = intval($row['tds']);
    echo json_encode(['status' => 'ok', 'reading' => $row]);
} else {
    echo json_encode([
        'status'  => 'ok',
        'reading' => ['temperature' => 0, 'ph' => 0, 'turbidity' => 0, 'tds' => 0, 'ts' => null]
    ]);
}
