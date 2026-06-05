const SerialPort = require('serialport');
const axios = require('axios');
const fs = require('fs');

const BAUD_RATE = 115200;
// Route directly to Django REST API (no PHP middleman)
const DJANGO_ENDPOINT = process.env.DJANGO_URL || 'http://localhost:8000/api/device/readings/';
const DEVICE_ID = process.env.DEVICE_ID || 'fishpond-01';
const DEVICE_TOKEN = process.env.DEVICE_TOKEN || 'cuXuqJvqQRevJTbejj6Iuf-dIKulTj18o4lkMAeuvVI';
const LOG_FILE = 'sensor_data.log';

// Sensor validation ranges
const VALID_RANGES = {
    temperature: { min: -10, max: 50 },
    ph: { min: 0, max: 14 },
    tds: { min: 0, max: 5000 },
    turbidity: { min: 0, max: 10 },
};

// Log to both console and file
function log(msg) {
    const timestamp = new Date().toLocaleTimeString();
    const fullMsg = `[${timestamp}] ${msg}`;
    console.log(fullMsg);
    fs.appendFileSync(LOG_FILE, fullMsg + '\n');
}

function validateReading(temp, ph, tds, turbidity) {
    const t = parseFloat(temp);
    const p = parseFloat(ph);
    const d = parseInt(tds, 10);
    const turb = parseFloat(turbidity);

    if (isNaN(t) || isNaN(p) || isNaN(d) || isNaN(turb)) {
        return { valid: false, reason: 'Non-numeric value detected' };
    }
    if (t < VALID_RANGES.temperature.min || t > VALID_RANGES.temperature.max)
        return { valid: false, reason: `Temperature ${t} out of range` };
    if (p < VALID_RANGES.ph.min || p > VALID_RANGES.ph.max)
        return { valid: false, reason: `pH ${p} out of range` };
    if (d < VALID_RANGES.tds.min || d > VALID_RANGES.tds.max)
        return { valid: false, reason: `TDS ${d} out of range` };
    if (turb < VALID_RANGES.turbidity.min || turb > VALID_RANGES.turbidity.max)
        return { valid: false, reason: `Turbidity ${turb} out of range` };

    return { valid: true, data: { temperature: t, ph: p, tds: d, turbidity: turb } };
}

async function findPort() {
    try {
        const ports = await SerialPort.SerialPort.list();
        log('Available ports: ' + ports.map(p => p.path).join(', '));
        // Prefer CH340/USB ports (common Arduino/ESP adapters)
        const preferred = ports.find(p =>
            (p.manufacturer || '').toLowerCase().includes('ch340') ||
            (p.pnpId || '').toLowerCase().includes('usb')
        );
        const selected = preferred || ports[0];
        return selected ? selected.path : 'COM3';
    } catch (e) {
        log('Using default COM3');
        return 'COM3';
    }
}

async function saveToDatabase(temp, ph, tds, turbidity) {
    const check = validateReading(temp, ph, tds, turbidity);
    if (!check.valid) {
        log(`✗ Validation failed: ${check.reason}`);
        return false;
    }

    try {
        log(`→ Saving: ${JSON.stringify(check.data)}`);
        const response = await axios.post(DJANGO_ENDPOINT, check.data, {
            timeout: 5000,
            headers: {
                'Content-Type': 'application/json',
                'X-Device-Id': DEVICE_ID,
                'X-Device-Token': DEVICE_TOKEN,
            }
        });

        if (response.status === 201) {
            log(`✓ Saved successfully`);
            return true;
        } else {
            log(`✗ HTTP ${response.status}`);
            return false;
        }
    } catch (error) {
        log(`✗ Save failed: ${error.message}`);
        return false;
    }
}

async function connectAndListen(comPort) {
    return new Promise((resolve) => {
        log(`Connecting to ${comPort}...`);

        const serialPort = new SerialPort.SerialPort({ path: comPort, baudRate: BAUD_RATE });
        const Readline = SerialPort.ReadlineParser;
        const parser = serialPort.pipe(new Readline({ delimiter: '\r\n' }));

        serialPort.on('open', () => {
            log(`✓ Connected to ${comPort} - Listening for data`);
        });

        parser.on('data', async (line) => {
            if (line.startsWith('DATA:')) {
                const dataStr = line.substring(5).trim();
                const parts = dataStr.split(',');
                if (parts.length === 4) {
                    const [temp, ph, tds, turbidity] = parts;
                    log(`📊 Raw: ${dataStr}`);
                    await saveToDatabase(temp, ph, tds, turbidity);
                }
            } else if (line.trim() && !line.includes('---')) {
                log(`  ${line}`);
            }
        });

        serialPort.on('error', (err) => {
            log(`✗ Serial error: ${err.message}`);
            serialPort.close();
            resolve(); // Trigger reconnect
        });

        serialPort.on('close', () => {
            log('✗ Port disconnected');
            resolve(); // Trigger reconnect
        });
    });
}

async function main() {
    log('=== Shrimply Smart Serial Listener ===');
    log('Will save all sensor readings to database continuously');
    log('Press Ctrl+C to stop\n');

    let comPort = await findPort();

    // Infinite retry loop
    while (true) {
        await connectAndListen(comPort);
        log(`⏳ Reconnecting in 3 seconds...\n`);
        await new Promise(resolve => setTimeout(resolve, 3000));
    }
}

main().catch(err => {
    log(`Fatal error: ${err.message}`);
    process.exit(1);
});
