import API_BASE from './apiConfig';

// WeMos HTTP API base URL.
// Recommended: set VITE_WEMOS_URL in `frontend/.env` (example: http://192.168.8.44)
// Fallback default matches `wemos_poller.py`.
const WEMOS_BASE = (import.meta.env.VITE_WEMOS_URL || 'http://192.168.8.44').replace(/\/$/, '');

function normalizeServo(raw) {
  const v = String(raw || '').trim().toUpperCase();
  if (v === 'ON' || v === 'OFF') return v;
  if (v === '1' || v === 'TRUE' || v === 'YES') return 'ON';
  if (v === '0' || v === 'FALSE' || v === 'NO') return 'OFF';
  return 'OFF';
}

function normalizeDistance(raw) {
  const v = String(raw || '').trim();
  if (!v || v.toUpperCase() === 'NA') return 'NA';
  const n = Number(v);
  return Number.isFinite(n) ? v : 'NA';
}

async function fetchTextWithTimeout(url, timeoutMs = 1500) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
      cache: 'no-store'
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.text();
  } finally {
    clearTimeout(timer);
  }
}

async function fetchJsonWithTimeout(url, timeoutMs = 1500) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(url, {
      method: 'GET',
      signal: controller.signal,
      cache: 'no-store'
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } finally {
    clearTimeout(timer);
  }
}

async function getLatestTelemetryFallback() {
  // Backend endpoint returns { motor_state, distance_cm, ... }
  const data = await fetchJsonWithTimeout(`${API_BASE}/latest-feeder-telemetry/`, 1500);
  return {
    motor_state: normalizeServo(data?.motor_state),
    distance_cm: (data?.distance_cm ?? 'NA')
  };
}

export const wemosApi = {
  baseUrl: WEMOS_BASE,

  async getServoSchedule() {
    // Backend proxy first
    try {
      return await fetchJsonWithTimeout(`${API_BASE}/feeder/servo_schedule/`, 1500);
    } catch {
      // Direct device fallback
      try {
        return await fetchJsonWithTimeout(`${WEMOS_BASE}/api/schedule`, 1500);
      } catch {
        return null;
      }
    }
  },

  async setServoSchedule({ openTime, closeTime, enabled }) {
    // Backend proxy first
    try {
      const token = localStorage.getItem('access_token');
      const headers = {
        'Content-Type': 'application/json'
      };
      if (token) headers.Authorization = `Bearer ${token}`;

      const resp = await fetch(`${API_BASE}/feeder/servo_schedule/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ openTime, closeTime, enabled })
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return await resp.json();
    } catch {
      // Direct device fallback: POST form to /setSchedule
      const params = new URLSearchParams();
      params.set('openTime', openTime);
      params.set('closeTime', closeTime);
      if (enabled) params.set('enabled', 'on');
      const resp = await fetch(`${WEMOS_BASE}/setSchedule`, {
        method: 'POST',
        body: params,
        cache: 'no-store'
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      // Try read schedule after setting
      return await fetchJsonWithTimeout(`${WEMOS_BASE}/api/schedule`, 1500);
    }
  },

  async ping() {
    try {
      // Preferred: talk directly to WeMos API.
      await fetchTextWithTimeout(`${WEMOS_BASE}/api/ping`, 1200);
      return { ok: true };
    } catch {
      // Fallback: if telemetry exists in backend, treat that as “online enough”.
      try {
        await getLatestTelemetryFallback();
        return { ok: true, via: 'backend' };
      } catch {
        return null;
      }
    }
  },

  async getServoState() {
    try {
      const raw = await fetchTextWithTimeout(`${WEMOS_BASE}/api/servo`, 1200);
      return normalizeServo(raw);
    } catch {
      const fb = await getLatestTelemetryFallback();
      return normalizeServo(fb.motor_state);
    }
  },

  async getDistance() {
    // Prefer backend proxy (avoids browser CORS/mixed-content issues)
    try {
      const data = await fetchJsonWithTimeout(`${API_BASE}/feeder/device_distance/`, 1500);
      if (data?.distance_cm == null) return 'NA';
      return normalizeDistance(String(data.distance_cm));
    } catch {
      // continue to direct device / DB fallback
    }
    try {
      const raw = await fetchTextWithTimeout(`${WEMOS_BASE}/api/distance`, 1200);
      return normalizeDistance(raw);
    } catch {
      const fb = await getLatestTelemetryFallback();
      if (fb.distance_cm == null) return 'NA';
      return normalizeDistance(String(fb.distance_cm));
    }
  },

  async servoOn() {
    // Prefer backend proxy (avoids browser CORS/mixed-content issues)
    try {
      const token = localStorage.getItem('access_token');
      const headers = {
        'Content-Type': 'application/json'
      };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      const resp = await fetch(`${API_BASE}/feeder/servo_on/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ device_id: 'web-control' })
      });
      if (resp.ok) return 'ON';
      throw new Error(`HTTP ${resp.status}`);
    } catch (e) {
      // Secondary fallback: try direct WeMos API (if available)
      try {
        await fetchTextWithTimeout(`${WEMOS_BASE}/api/servo/on`, 1500);
        return 'ON';
      } catch {
        // If using the simple ESP8266 web server sketch, it might expose /open
        try {
          await fetchTextWithTimeout(`${WEMOS_BASE}/open`, 1500);
          return 'ON';
        } catch (e2) {
          console.error('Servo ON failed on both backend and device:', e, e2);
          throw e;
        }
      }
    }
  },

  async servoOff() {
    try {
      const token = localStorage.getItem('access_token');
      const headers = {
        'Content-Type': 'application/json'
      };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
      const resp = await fetch(`${API_BASE}/feeder/servo_off/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ device_id: 'web-control' })
      });
      if (resp.ok) return 'OFF';
      throw new Error(`HTTP ${resp.status}`);
    } catch (e) {
      try {
        await fetchTextWithTimeout(`${WEMOS_BASE}/api/servo/off`, 1500);
        return 'OFF';
      } catch {
        try {
          await fetchTextWithTimeout(`${WEMOS_BASE}/close`, 1500);
          return 'OFF';
        } catch (e2) {
          console.error('Servo OFF failed on both backend and device:', e, e2);
          throw e;
        }
      }
    }
  }
};

export default wemosApi;
