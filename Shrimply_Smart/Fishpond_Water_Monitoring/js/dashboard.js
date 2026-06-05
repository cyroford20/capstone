// Fetch latest reading (no dummy data, no up/down buttons)
async function refreshReadings() {
    try {
        const res = await fetch('get_latest.php');
        const json = await res.json();
        if (json.status === 'ok' && json.reading) {
            const r = json.reading;
            document.getElementById('temp').textContent = parseFloat(r.temp).toFixed(2) + ' °C';
            document.getElementById('ph').textContent = parseFloat(r.ph).toFixed(2);
            document.getElementById('tds').textContent = parseFloat(r.tds).toFixed(2) + ' ppm';
            document.getElementById('ts').textContent = r.ts;
        } else {
            document.getElementById('temp').textContent = '-- °C';
            document.getElementById('ph').textContent = '--';
            document.getElementById('tds').textContent = '-- ppm';
            document.getElementById('ts').textContent = '--';
        }
    } catch (e) {
        console.error('Failed to fetch readings', e);
    }
}

setInterval(refreshReadings, 5000);
refreshReadings();
