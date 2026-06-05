<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

// Handle preflight
if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

require_once __DIR__ . '/config.php';

// Accept both form-encoded POST and raw JSON body
$input = $_POST;
if (empty($input) || (!isset($input['temp']) && !isset($input['temperature']))) {
    $raw = file_get_contents('php://input');
    $decoded = json_decode($raw, true);
    if (is_array($decoded)) $input = $decoded;
}

// Map field names (Arduino may send temp/ph/tds/turbidity or temperature/ph/tds/turbidity)
$temp   = $input['temp']   ?? $input['temperature'] ?? null;
$ph     = $input['ph']     ?? null;
$turbidity = $input['turbidity'] ?? $input['turb'] ?? 0;
$tds    = $input['tds']    ?? null;
$token  = $input['token']  ?? null;

if ($temp === null || $ph === null || $tds === null) {
    echo json_encode(['status' => 'error', 'message' => 'Missing fields: temp, ph, tds required']);
    http_response_code(400);
    exit;
}

// Token check (disabled when API_TOKEN is empty)
if (defined('API_TOKEN') && API_TOKEN !== '' && $token !== API_TOKEN) {
    echo json_encode(['status' => 'error', 'message' => 'Invalid token']);
    http_response_code(401);
    exit;
}

if (!is_numeric($temp) || !is_numeric($ph) || !is_numeric($tds) || !is_numeric($turbidity)) {
    echo json_encode(['status' => 'error', 'message' => 'Invalid numeric values']);
    http_response_code(400);
    exit;
}

$mysqli = new mysqli(DB_HOST, DB_USER, DB_PASS, DB_NAME);
if ($mysqli->connect_errno) {
    echo json_encode(['status' => 'error', 'message' => 'DB connection failed: ' . $mysqli->connect_error]);
    http_response_code(500);
    exit;
}

$stmt = $mysqli->prepare("INSERT INTO api_sensorreading (temperature, ph, turbidity, tds, timestamp) VALUES (?, ?, ?, ?, NOW(3))");
if (!$stmt) {
    echo json_encode(['status' => 'error', 'message' => 'Prepare failed: ' . $mysqli->error]);
    http_response_code(500);
    $mysqli->close();
    exit;
}

$t = floatval($temp);
$p = floatval($ph);
$o = floatval($turbidity);

$d = intval($tds);
$stmt->bind_param('dddi', $t, $p, $o, $d);

if ($stmt->execute()) {
    echo json_encode([
        'status' => 'ok',
        'id'     => $stmt->insert_id,
        'temp'   => $t,
        'ph'     => $p,
        'turbidity' => $o,
        'tds'    => $d
    ]);
    http_response_code(201);
} else {
    echo json_encode(['status' => 'error', 'message' => 'Insert failed: ' . $stmt->error]);
    http_response_code(500);
}

$stmt->close();
$mysqli->close();
