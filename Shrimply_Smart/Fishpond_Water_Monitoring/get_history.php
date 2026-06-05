<?php

/**
 * get_history.php — Return historical sensor readings for charts
 *
 * Query params:
 *   ?days=7      Number of days of history (default 7, max 90)
 *   ?limit=500   Max rows to return (default 500, max 5000)
 */
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');

require_once __DIR__ . '/config.php';

$days  = isset($_GET['days'])  ? min(max(intval($_GET['days']), 1), 90)    : 7;
$limit = isset($_GET['limit']) ? min(max(intval($_GET['limit']), 1), 5000) : 500;

$mysqli = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
if ($mysqli->connect_errno) {
    http_response_code(500);
    echo json_encode(['status' => 'error', 'message' => 'DB connection failed']);
    exit;
}

$stmt = $mysqli->prepare(
    "SELECT id, timestamp, temperature, ph, turbidity, tds
     FROM api_sensorreading
     WHERE timestamp >= NOW() - INTERVAL ? DAY
     ORDER BY timestamp ASC
     LIMIT ?"
);
$stmt->bind_param('ii', $days, $limit);
$stmt->execute();
$result = $stmt->get_result();

$rows = [];
while ($r = $result->fetch_assoc()) {
    $r['temperature'] = floatval($r['temperature']);
    $r['ph']          = floatval($r['ph']);
    $r['turbidity']      = floatval($r['turbidity']);
    $r['tds']         = intval($r['tds']);
    $rows[] = $r;
}

$result->free();
$stmt->close();
$mysqli->close();

echo json_encode(['status' => 'ok', 'count' => count($rows), 'readings' => $rows]);
