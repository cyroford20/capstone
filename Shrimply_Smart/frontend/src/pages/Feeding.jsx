import { useEffect, useRef, useState } from 'react';
import { useLanguage } from '../context/LanguageContext';
import {
  DEFAULT_FEEDER_STATE,
  capacityPercent,
  fetchFeederState,
  updateFeederSettings,
  toggleAutoFeeding,
  feedOnce,
  refillFeeder,
  processAutoFeedTick,
  fetchFeedingHistory
} from '../services/feeder';
import { wemosApi } from '../services/wemos';
import { getChannelsWebSocketUrl } from '../services/apiConfig';
import { alertWebSocket } from '../services/alertWebSocket';

function Toggle({ checked, onChange, label }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${checked ? 'bg-gradient-to-r from-blue-500 to-blue-600' : 'bg-gray-300'
        }`}
      aria-pressed={checked}
      aria-label={label}
    >
      <span
        className={`inline-block h-6 w-6 transform rounded-full bg-white shadow-lg transition-transform ${checked ? 'translate-x-7' : 'translate-x-1'
          }`}
      />
    </button>
  );
}

function Stat({ label, value, sub, icon }) {
  return (
    <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-white to-gray-50 p-6 shadow-md border border-gray-100 hover:shadow-lg transition-all duration-300">
      {icon && <div className="absolute top-4 right-4 text-3xl opacity-20">{icon}</div>}
      <div className="text-sm font-medium text-gray-600 uppercase tracking-wide">{label}</div>
      <div className="mt-2 text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-gray-500">{sub}</div>}
    </div>
  );
}

function useInterval(callback, delay) {
  const savedCallback = useRef();
  useEffect(() => { savedCallback.current = callback; }, [callback]);
  useEffect(() => {
    if (delay == null) return;
    const id = setInterval(() => savedCallback.current && savedCallback.current(), delay);
    return () => clearInterval(id);
  }, [delay]);
}

export default function Feeding() {
  const { t } = useLanguage();
  const [state, setState] = useState(() => DEFAULT_FEEDER_STATE);
  const [now, setNow] = useState(Date.now());
  const [feedingHistory, setFeedingHistory] = useState([]);
  const [activeTab, setActiveTab] = useState('controls');
  const [newDailyTime, setNewDailyTime] = useState('08:00');
  const [servoState, setServoState] = useState('OFF');
  const [ultrasonicDistance, setUltrasonicDistance] = useState('NA');
  const [wemosOnline, setWemosOnline] = useState(false);
  const [lastTelemetryTimestamp, setLastTelemetryTimestamp] = useState(null);
  const [servoLoading, setServoLoading] = useState(false);
  const [servoScheduleOpenTime, setServoScheduleOpenTime] = useState('08:00');
  const [servoScheduleCloseTime, setServoScheduleCloseTime] = useState('18:00');
  const [servoScheduleEnabled, setServoScheduleEnabled] = useState(false);
  const [servoScheduleSaving, setServoScheduleSaving] = useState(false);
  const [toast, setToast] = useState(null);

  const flash = (msg, type = 'error') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  // UI only supports interval + daily scheduling.
  // If backend ever returns another value, default to interval.
  const effectiveScheduleType = state.scheduleType === 'daily' ? 'daily' : 'interval';

  // Fetch schedule once (live telemetry uses WebSocket)
  const fetchWemosData = async () => {
    try {
      const schedule = await wemosApi.getServoSchedule().catch(() => null);

      if (schedule) {
        const open = schedule.open_time || schedule.openTime;
        const close = schedule.close_time || schedule.closeTime;
        if (open) setServoScheduleOpenTime(open);
        if (close) setServoScheduleCloseTime(close);
        setServoScheduleEnabled(Boolean(schedule.enabled));
      }
    } catch (error) {
      console.error('Failed to fetch Wemos data:', error);
    }
  };

  // Fetch initial state from backend
  useEffect(() => {
    const loadData = async () => {
      try {
        const [feederState, history] = await Promise.all([
          fetchFeederState(),
          fetchFeedingHistory(20)
        ]);
        setState(feederState);
        setFeedingHistory(history);
      } catch (error) {
        console.error('Failed to load feeder data:', error);
        // Keep default state
      }
    };
    loadData();

    // One-time schedule fetch
    fetchWemosData();

    // Initial fallback telemetry (helps even before WS connects)
    (async () => {
      try {
        const [dist, servo] = await Promise.all([
          wemosApi.getDistance().catch(() => 'NA'),
          wemosApi.getServoState().catch(() => null)
        ]);
        if (dist) setUltrasonicDistance(dist);
        if (servo) setServoState(servo);
      } catch {
        // ignore
      }
    })();

    // Live feeder telemetry push (no polling)
    let ws = null;
    let reconnectTimeout = null;
    const WS_URL = getChannelsWebSocketUrl('/ws/feeder/');

    const connectWebSocket = () => {
      try {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
          setWemosOnline(true);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            if (data.timestamp) {
              setLastTelemetryTimestamp(data.timestamp);
            }

            const motor = (data.motor_state ?? data.motorState ?? data.servo_state ?? data.servoState);
            if (motor !== undefined && motor !== null && String(motor).trim() !== '') {
              const normalized = String(motor).trim().toUpperCase();
              setServoState(normalized === 'ON' ? 'ON' : 'OFF');
            }

            if (data.distance_cm !== undefined) {
              if (data.distance_cm === null || data.distance_cm === '') {
                setUltrasonicDistance('NA');
              } else {
                const n = Number(data.distance_cm);
                setUltrasonicDistance(Number.isFinite(n) ? String(Math.round(n * 10) / 10) : 'NA');
              }
            }
          } catch (err) {
            console.warn('[WS_FEEDER] Failed to parse message:', err);
          }
        };

        ws.onclose = () => {
          setWemosOnline(false);
          reconnectTimeout = setTimeout(connectWebSocket, 5000);
        };

        ws.onerror = (err) => {
          console.warn('[WS_FEEDER] Error:', err);
          try {
            ws.close();
          } catch {
            // ignore
          }
        };
      } catch (err) {
        console.warn('[WS_FEEDER] Could not connect:', err);
        setWemosOnline(false);
        reconnectTimeout = setTimeout(connectWebSocket, 5000);
      }
    };

    connectWebSocket();

    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, []);

  useEffect(() => {
    const seenAlerts = new Set();

    const onAlert = (data) => {
      const alert = data?.alert;
      if (!alert || !alert.id || seenAlerts.has(alert.id)) return;
      seenAlerts.add(alert.id);

      if (alert.parameter === 'feeder_connection' || alert.parameter === 'feeder_capacity') {
        flash(alert.message || 'Feeder alert received', 'error');
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification('🚨 Feeder Alert', {
            body: `${alert.parameter}: ${alert.message}`,
            icon: '/alert-icon.png'
          });
        }
      }
    };

    alertWebSocket.connect(onAlert);
    return () => {
      alertWebSocket.disconnect();
    };
  }, []);

  // Fallback polling: when WS is disconnected, poll device/backend for distance.
  // This makes the Feeding page show ultrasonic distance even if the feeder WS is down.
  useInterval(async () => {
    if (wemosOnline) return;
    try {
      const [dist, servo] = await Promise.all([
        wemosApi.getDistance().catch(() => 'NA'),
        wemosApi.getServoState().catch(() => null)
      ]);
      if (dist) setUltrasonicDistance(dist);
      if (servo) setServoState(servo);
    } catch {
      // ignore
    }
  }, wemosOnline ? null : 2000);

  // Migration: remove legacy 'adaptive' schedule type.
  useEffect(() => {
    if (state.scheduleType !== 'adaptive') return;
    updateFeederSettings({ schedule_type: 'interval' })
      .then((updated) => setState(updated))
      .catch((error) => console.error('Failed to migrate schedule type:', error));
  }, [state.scheduleType]);
  // Tick every 30 seconds: update time and process auto feed events
  useInterval(async () => {
    setNow(Date.now());
    try {
      const updatedState = await processAutoFeedTick();
      if (updatedState && updatedState.id) {
        setState(updatedState);
        // Refresh history every other tick (~60 seconds)
        if (now % 60000 < 30000) {
          const history = await fetchFeedingHistory(20);
          setFeedingHistory(history);
        }
      }
    } catch (error) {
      console.error('Failed to process auto feed:', error);
    }
  }, 30000);

  useInterval(() => {
    setNow(Date.now());
  }, 1000);

  const telemetryAgeMs = lastTelemetryTimestamp ? (now - new Date(lastTelemetryTimestamp).getTime()) : Number.POSITIVE_INFINITY;
  const deviceConnected = Number.isFinite(telemetryAgeMs) && telemetryAgeMs >= 0 && telemetryAgeMs <= 20000;
  const capPct = capacityPercent(state);
  const lowThreshold = Number(state.lowPercent ?? state.low_percent ?? 15);
  const lowFeed = capPct <= lowThreshold;

  const prevDeviceConnected = useRef(null);
  const prevLowFeed = useRef(null);

  useEffect(() => {
    if (prevDeviceConnected.current === true && deviceConnected === false) {
      flash(t('deviceDisconnected') || 'Device disconnected', 'error');
      if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('⚠️ Device Disconnected', { body: 'Feeder device is offline.' });
      }
    }
    prevDeviceConnected.current = deviceConnected;
  }, [deviceConnected, t]);

  useEffect(() => {
    const alertsEnabled = (state.alertsEnabled !== false && state.alerts_enabled !== false);
    const lowFeedEnabled = (state.lowFeedAlert !== false && state.low_feed_alert !== false);

    if (alertsEnabled && lowFeedEnabled) {
      if (prevLowFeed.current === false && lowFeed === true) {
        flash(t('lowFeed') || `Low feed: ${capPct}% remaining`, 'error');
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification('🍤 Low Feed', { body: `Feeder capacity low (${capPct}%).` });
        }
      }
    }
    prevLowFeed.current = lowFeed;
  }, [lowFeed, capPct, state.alertsEnabled, state.alerts_enabled, state.lowFeedAlert, state.low_feed_alert, t]);

  return (
    <div className="p-8 modern-bg min-h-full">
      {/* Hero Header */}
      <div className="mb-8 relative">
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 rounded-2xl"></div>
        <div className="relative z-10 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-gradient mb-2">{t('feedingManagement')}</h1>
              <p className="text-slate-600 text-lg">{t('feedingSubtitle')}</p>
            </div>
            <div className="hidden md:block" style={{ backgroundImage: "url('/shrimp_pond_pic/raw-shrimps-on-hand-washing-shrimp-on-bowl-shrimps-background-fresh-shrimp-prawns-for-cooking-seafood-food-in-the-kitchen-free-photo.jpg')" }}>
            </div>
          </div>
        </div>
      </div>

      {/* Status Overview */}
      <div className="grid-modern mb-8">
        <div className="metric-card-modern">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 rounded-xl bg-gradient-to-r from-green-500 to-teal-500 text-white shadow-lg">
              <span className="text-2xl">⏰</span>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-slate-800">{state.status === 'scheduled' ? t('active') : state.status === 'due' ? t('due') : t('manual')}</div>
              <div className="text-sm text-slate-500">{t('mode')}</div>
            </div>
          </div>
          <h3 className="text-lg font-semibold text-slate-800 mb-1">{t('feedingStatus')}</h3>
          <div className="text-sm text-slate-600">
            {state.nextFeedTime ? `${t('nextFeed')}: ${new Date(state.nextFeedTime).toLocaleString()}` : t('noScheduleSet')}
          </div>
        </div>

        <div className="metric-card-modern">
          <div className="flex items-center justify-between mb-4">
            <div className="p-3 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-lg">
              <span className="text-2xl">📈</span>
            </div>
            <div className="text-right">
              <div className="text-3xl font-bold text-slate-800">{feedingHistory.length}</div>
              <div className="text-sm text-slate-500">{t('totalFeeds')}</div>
            </div>
          </div>
          <h3 className="text-lg font-semibold text-slate-800 mb-1">{t('feedHistory')}</h3>
          <div className="text-sm text-slate-600">
            {state.lastFedAt ? `${t('lastFeed')}: ${new Date(state.lastFedAt).toLocaleString()}` : t('noFeedsYet')}
          </div>
        </div>
      </div>

      {/* Empty Storage Alert */}
      {(state.capacityCurrent || state.capacity_current) <= 0 && (
        <div className="mb-6 relative overflow-hidden rounded-2xl bg-gradient-to-r from-red-500 to-orange-500 p-6 shadow-lg border-2 border-red-600">
          <div className="absolute inset-0 opacity-10">
            <div className="absolute top-0 right-0 w-40 h-40 bg-white rounded-full -mr-20 -mt-20"></div>
          </div>
          <div className="relative z-10 flex items-center gap-4">
            <div className="text-5xl">⚠️</div>
            <div>
              <h2 className="text-2xl font-bold text-white mb-1">{t('feedStorageEmpty') || 'Feed Storage Empty'}</h2>
              <p className="text-red-50 text-base">{t('feedStorageEmptyMsg') || 'Your feed storage is empty. Please refill the feeder to continue automatic feeding.'}</p>
            </div>
            <button
              onClick={async () => {
                try {
                  const updatedState = await refillFeeder();
                  setState(updatedState);
                } catch (error) {
                  console.error('Failed to refill feeder:', error);
                }
              }}
              className="ml-auto px-6 py-3 bg-white text-red-600 font-bold rounded-xl hover:bg-red-50 transition-all shadow-lg whitespace-nowrap"
            >
              🔄 {t('refillNow') || 'Refill Now'}
            </button>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="mb-6">
        <div className="flex space-x-1 bg-slate-100 p-1 rounded-lg">
          {[
            { id: 'controls', label: t('controls'), icon: '🎛️' },
            { id: 'schedule', label: t('schedule'), icon: '📅' },
            { id: 'settings', label: t('settings'), icon: '⚙️' },
            { id: 'history', label: t('history'), icon: '📋' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center px-4 py-2 rounded-md text-sm font-medium transition-all ${activeTab === tab.id
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
                }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {activeTab === 'controls' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Auto Mode Toggle */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-green-50 to-emerald-50 p-6 shadow-lg border border-green-100">
              <div className="absolute bottom-0 left-0 w-40 h-40 bg-gradient-to-tr from-green-200/20 to-transparent rounded-full -ml-20 -mb-20"></div>
              <h3 className="text-xl font-bold text-slate-800 mb-5 flex items-center">
                <span className="mr-2 text-2xl">⚡</span>
                {t('autoFeedingMode')}
              </h3>
              <div className="space-y-4 relative z-10">
                <div className="flex items-center justify-between p-4 rounded-xl bg-white/60 backdrop-blur-sm border border-slate-200">
                  <span className="text-base font-semibold text-slate-800">{t('autoFeeding')}</span>
                  <Toggle
                    checked={state.autoEnabled !== false && state.auto_enabled !== false}
                    onChange={async (value) => {
                      try {
                        const updatedState = await toggleAutoFeeding(value);
                        setState(updatedState);
                      } catch (error) {
                        console.error('Failed to toggle auto feeding:', error);
                      }
                    }}
                    label="Auto Feeding Toggle"
                  />
                </div>
                {(state.autoEnabled !== false && state.auto_enabled !== false) && (
                  <div className="p-4 bg-gradient-to-r from-green-500 to-emerald-500 rounded-xl shadow-md text-white">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="text-sm font-semibold opacity-90 mb-1">{t('nextFeed')}</div>
                        <div className="text-lg font-bold">
                          {state.nextFeedTime ? new Date(state.nextFeedTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : t('calculating')}
                        </div>
                      </div>
                      <div className="text-2xl">⏰</div>
                    </div>
                    <div className="mt-2 text-xs bg-white/20 rounded-lg px-3 py-2 backdrop-blur-sm">
                      {t('mode')}: {effectiveScheduleType === 'daily' ? '📅 ' + t('daily') : '⚙️ ' + t('interval')}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Hardware Controls - Servo and Ultrasonic */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-orange-50 to-red-50 p-6 shadow-lg border border-orange-100">
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-bl from-orange-200/20 to-transparent rounded-full -mr-16 -mt-16"></div>
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-xl font-bold text-slate-800 flex items-center">
                  <span className="mr-2 text-2xl">⚙️</span>
                  Hardware Controls
                </h3>
              </div>
              <div className="space-y-4">
                {/* Wemos Status */}
                <div className="p-3 rounded-lg bg-white/60 backdrop-blur-sm border border-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Wemos Status:</span>
                    <div className="flex items-center gap-2">
                      <div className={`w-3 h-3 rounded-full animate-pulse ${deviceConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
                      <span className="text-sm font-medium text-slate-700">
                        {deviceConnected ? '🟢 Online' : '🔴 Offline'}
                      </span>
                    </div>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Telemetry age: {lastTelemetryTimestamp ? `${Math.round(telemetryAgeMs / 1000)}s` : 'No data'}
                  </div>
                </div>

                {/* Ultrasonic Distance */}
                <div className="p-3 rounded-lg bg-white/60 backdrop-blur-sm border border-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Ultrasonic Distance:</span>
                    <span className="text-lg font-bold text-slate-800">
                      {ultrasonicDistance === 'NA' ? '📏 N/A' : `📏 ${ultrasonicDistance} cm`}
                    </span>
                  </div>
                </div>

                {/* Servo Schedule (ON/OFF Time) */}
                <div className="p-3 rounded-lg bg-white/60 backdrop-blur-sm border border-slate-200 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Servo Schedule:</span>
                    <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        checked={servoScheduleEnabled}
                        onChange={(e) => setServoScheduleEnabled(e.target.checked)}
                      />
                      Enable
                    </label>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <div className="text-xs text-slate-600 font-medium">ON time</div>
                      <input
                        type="time"
                        value={servoScheduleOpenTime}
                        onChange={(e) => setServoScheduleOpenTime(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                      />
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs text-slate-600 font-medium">OFF time</div>
                      <input
                        type="time"
                        value={servoScheduleCloseTime}
                        onChange={(e) => setServoScheduleCloseTime(e.target.value)}
                        className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                      />
                    </div>
                  </div>
                  <button
                    onClick={async () => {
                      if (servoScheduleSaving) return;
                      try {
                        setServoScheduleSaving(true);
                        const result = await wemosApi.setServoSchedule({
                          openTime: servoScheduleOpenTime,
                          closeTime: servoScheduleCloseTime,
                          enabled: servoScheduleEnabled
                        });
                        if (result) {
                          const open = result.open_time || result.openTime;
                          const close = result.close_time || result.closeTime;
                          if (open) setServoScheduleOpenTime(open);
                          if (close) setServoScheduleCloseTime(close);
                          setServoScheduleEnabled(Boolean(result.enabled));
                        }
                      } catch (e) {
                        console.error('Failed to save servo schedule:', e);
                      } finally {
                        setServoScheduleSaving(false);
                      }
                    }}
                    className="w-full rounded-xl bg-gradient-to-r from-blue-600 to-cyan-600 text-white font-semibold py-2.5 px-4 shadow-lg hover:shadow-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    disabled={servoScheduleSaving}
                  >
                    {servoScheduleSaving ? 'Saving...' : 'Save Schedule'}
                  </button>
                </div>

                {/* Servo Control Buttons */}
                <div className="grid grid-cols-2 gap-3">
                  <button
                    className="relative overflow-hidden rounded-xl bg-gradient-to-r from-red-600 to-pink-600 text-white font-semibold py-3 px-4 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                    onClick={async () => {
                      if (servoLoading) return;
                      try {
                        setServoLoading(true);
                        await wemosApi.servoOff();
                        setServoState('OFF');
                      } catch (error) {
                        console.error('Failed to turn servo OFF:', error);
                      } finally {
                        setServoLoading(false);
                      }
                    }}
                    disabled={servoLoading}
                  >
                    {servoLoading ? (
                      <>
                        <span className="mr-2 animate-spin">⚙️</span>
                        <span>Loading...</span>
                      </>
                    ) : (
                      <>
                        <span className="mr-2 text-lg">❌</span>
                        <span>Servo OFF</span>
                      </>
                    )}
                  </button>
                  <button
                    className="relative overflow-hidden rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 text-white font-semibold py-3 px-4 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                    onClick={async () => {
                      if (servoLoading) return;
                      try {
                        setServoLoading(true);
                        await wemosApi.servoOn();
                        setServoState('ON');
                      } catch (error) {
                        console.error('Failed to turn servo ON:', error);
                      } finally {
                        setServoLoading(false);
                      }
                    }}
                    disabled={servoLoading}
                  >
                    {servoLoading ? (
                      <>
                        <span className="mr-2 animate-spin">⚙️</span>
                        <span>Loading...</span>
                      </>
                    ) : (
                      <>
                        <span className="mr-2 text-lg">✅</span>
                        <span>Servo ON</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Current Servo State */}
                <div className="p-3 rounded-lg bg-white/60 backdrop-blur-sm border border-slate-200">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Servo State:</span>
                    <span className={`text-lg font-bold flex items-center gap-2 ${servoState === 'ON' ? 'text-green-600' : 'text-red-600'}`}>
                      <span className="text-xl">{servoState === 'ON' ? '✅' : '❌'}</span>
                      {servoState}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'schedule' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Feeding Schedule */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-blue-50 to-cyan-50 p-6 shadow-lg border border-blue-100">
              <div className="absolute top-0 right-0 w-32 h-32 bg-gradient-to-br from-blue-200/20 to-transparent rounded-full -mr-16 -mt-16"></div>
              <h3 className="text-xl font-bold text-slate-800 mb-5 flex items-center relative z-10">
                <span className="mr-2 text-2xl">📅</span>
                {t('schedule')}
              </h3>
              <div className="space-y-4 relative z-10">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">Schedule Type</label>
                  <select
                    className="w-full border-2 border-blue-200 rounded-xl px-4 py-3 text-base font-semibold focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all bg-white"
                    value={effectiveScheduleType}
                    onChange={async (e) => {
                      try {
                        const updatedState = await updateFeederSettings({ schedule_type: e.target.value });
                        setState(updatedState);
                      } catch (error) {
                        console.error('Failed to update schedule type:', error);
                      }
                    }}
                  >
                    <option value="interval">Interval</option>
                    <option value="daily">Daily</option>
                  </select>
                </div>

                {effectiveScheduleType === 'interval' && (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">Interval (minutes)</label>
                      <input
                        type="number"
                        className="w-full border-2 border-blue-200 rounded-xl px-4 py-3 text-base font-semibold focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all"
                        value={state.intervalMinutes || 60}
                        onChange={async (e) => {
                          try {
                            const minutes = Math.max(1, Number(e.target.value || 1));
                            const updatedState = await updateFeederSettings({ interval_minutes: minutes });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to update interval:', error);
                          }
                        }}
                        min={1}
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">{t('portionPerFeed') || 'Portion per Feed (grams)'}</label>
                      <input
                        type="number"
                        className="w-full border-2 border-blue-200 rounded-xl px-4 py-3 text-base font-semibold focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all"
                        value={state.portionGrams || 50}
                        onChange={async (e) => {
                          try {
                            const grams = Math.max(1, Number(e.target.value || 1));
                            const updatedState = await updateFeederSettings({ portion_grams: grams });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to update portion grams:', error);
                          }
                        }}
                        min={1}
                      />
                    </div>
                  </div>
                )}

                {effectiveScheduleType === 'daily' && (
                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-bold text-slate-700 mb-2">{t('portionPerFeed') || 'Portion per Feed (grams)'}</label>
                      <input
                        type="number"
                        className="w-full border-2 border-blue-200 rounded-xl px-4 py-3 text-base font-semibold focus:border-blue-500 focus:ring-4 focus:ring-blue-100 transition-all"
                        value={state.portionGrams || 50}
                        onChange={async (e) => {
                          try {
                            const grams = Math.max(1, Number(e.target.value || 1));
                            const updatedState = await updateFeederSettings({ portion_grams: grams });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to update portion grams:', error);
                          }
                        }}
                        min={1}
                      />
                    </div>

                    <div className="text-sm font-bold text-slate-700">Daily Times</div>
                    <div className="space-y-2">
                      {(state.dailySchedule || []).length === 0 ? (
                        <div className="text-sm text-slate-500">No times set.</div>
                      ) : (
                        (state.dailySchedule || []).map((timeStr) => (
                          <div key={timeStr} className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-200">
                            <div className="font-semibold text-slate-800">⏰ {timeStr}</div>
                            <button
                              onClick={async () => {
                                try {
                                  const newSchedule = (state.dailySchedule || []).filter(ti => ti !== timeStr);
                                  const updatedState = await updateFeederSettings({ daily_schedule: newSchedule });
                                  setState(updatedState);
                                } catch (error) {
                                  console.error('Failed to remove time:', error);
                                }
                              }}
                              className="px-3 py-1 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-semibold"
                            >
                              Remove
                            </button>
                          </div>
                        ))
                      )}
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="time"
                        value={newDailyTime}
                        onChange={(e) => setNewDailyTime(e.target.value)}
                        className="flex-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
                      />
                      <button
                        onClick={async () => {
                          try {
                            const currentTimes = (state.dailySchedule || []).filter(ti => ti && ti.trim());
                            const next = newDailyTime;
                            if (!next || !next.trim()) return;
                            if (currentTimes.includes(next)) return;
                            const newSchedule = [...currentTimes, next].sort();
                            const updatedState = await updateFeederSettings({ daily_schedule: newSchedule });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to add time:', error);
                          }
                        }}
                        className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold"
                      >
                        Add
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Weather Adaptation */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-green-50 to-emerald-50 p-6 shadow-lg border border-green-100">
              <div className="absolute bottom-0 left-0 w-40 h-40 bg-gradient-to-tr from-green-200/20 to-transparent rounded-full -ml-20 -mb-20"></div>
              <h3 className="text-xl font-bold text-slate-800 mb-5 flex items-center relative z-10">
                <span className="mr-2 text-2xl">☁️</span>
                Weather Adaptation
              </h3>
              <div className="space-y-4 relative z-10">
                <label className="flex items-center p-4 bg-white rounded-xl border-2 border-slate-200 cursor-pointer hover:border-green-300 transition-all">
                  <input
                    type="checkbox"
                    checked={state.weatherAdaptation || false}
                    onChange={async (e) => {
                      try {
                        const updatedState = await updateFeederSettings({ weather_adaptation: e.target.checked });
                        setState(updatedState);
                      } catch (error) {
                        console.error('Failed to update weather adaptation:', error);
                      }
                    }}
                    className="w-5 h-5 mr-3 accent-green-500"
                  />
                  <span className="text-base font-semibold text-slate-800">Enable weather adaptation</span>
                </label>

                {state.weatherAdaptation && (
                  <div className="space-y-4 p-4 bg-gradient-to-r from-green-500 to-teal-500 rounded-xl shadow-lg">
                    <div>
                      <label className="block text-sm font-bold text-white mb-2">Rain reduction (%)</label>
                      <input
                        type="number"
                        className="w-full border-2 border-white/30 bg-white/90 rounded-lg px-4 py-2 text-base font-semibold focus:ring-4 focus:ring-white/50"
                        value={state.rainReductionPercent || 20}
                        onChange={async (e) => {
                          try {
                            const updatedState = await updateFeederSettings({ rain_reduction_percent: Number(e.target.value) });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to update rain reduction:', error);
                          }
                        }}
                        min={0}
                        max={100}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-bold text-white mb-2">Heat increase (%)</label>
                      <input
                        type="number"
                        className="w-full border-2 border-white/30 bg-white/90 rounded-lg px-4 py-2 text-base font-semibold focus:ring-4 focus:ring-white/50"
                        value={state.heatIncreasePercent || 10}
                        onChange={async (e) => {
                          try {
                            const updatedState = await updateFeederSettings({ heat_increase_percent: Number(e.target.value) });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to update heat increase:', error);
                          }
                        }}
                        min={0}
                        max={100}
                      />
                    </div>
                    <label className="flex items-center p-3 bg-white/20 backdrop-blur-sm rounded-lg cursor-pointer hover:bg-white/30 transition-all">
                      <input
                        type="checkbox"
                        checked={state.extremeWeatherPause !== false}
                        onChange={async (e) => {
                          try {
                            const updatedState = await updateFeederSettings({ extreme_weather_pause: e.target.checked });
                            setState(updatedState);
                          } catch (error) {
                            console.error('Failed to update extreme weather pause:', error);
                          }
                        }}
                        className="w-5 h-5 mr-3 accent-white"
                      />
                      <span className="text-sm font-semibold text-white">Pause in extreme weather</span>
                    </label>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'settings' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Basic Settings */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-indigo-50 to-purple-50 p-6 shadow-lg border border-indigo-100">
              <div className="absolute top-0 left-0 w-32 h-32 bg-gradient-to-br from-indigo-200/20 to-transparent rounded-full -ml-16 -mt-16"></div>
              <h3 className="text-xl font-bold text-slate-800 mb-5 flex items-center relative z-10">
                <span className="mr-2 text-2xl">⚙️</span>
                {t('basicSettings')}
              </h3>
              <div className="space-y-4 relative z-10">
                <div>
                  <label className="block text-sm font-bold text-slate-700 mb-2">🍤 {t('portionPerFeed')}</label>
                  <input
                    type="number"
                    className="w-full border-2 border-indigo-200 rounded-xl px-4 py-3 text-base font-semibold focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100 transition-all"
                    value={state.portionGrams || state.portion_grams}
                    onChange={async (e) => {
                      try {
                        const updatedState = await updateFeederSettings({ portion_grams: Number(e.target.value) });
                        setState(updatedState);
                      } catch (error) {
                        console.error('Failed to update portion:', error);
                      }
                    }}
                    min={0}
                  />
                </div>
              </div>
            </div>

            {/* Alert Settings */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-red-50 to-orange-50 p-6 shadow-lg border border-red-100">
              <div className="absolute bottom-0 right-0 w-40 h-40 bg-gradient-to-tl from-red-200/20 to-transparent rounded-full -mr-20 -mb-20"></div>
              <h3 className="text-xl font-bold text-slate-800 mb-5 flex items-center relative z-10">
                <span className="mr-2 text-2xl">🔔</span>
                {t('alertSettings')}
              </h3>
              <div className="space-y-3 relative z-10">
                {[
                  { key: 'alertsEnabled', label: t('enableAlerts'), field: 'alerts_enabled', icon: '✅' },
                  { key: 'weatherAlert', label: t('weatherChangeAlerts'), field: 'weather_alert', icon: '☁️' }
                ].map(alert => (
                  <label
                    key={alert.key}
                    className="flex items-center p-4 bg-white rounded-xl border-2 border-slate-200 cursor-pointer hover:border-red-300 hover:shadow-md transition-all"
                  >
                    <input
                      type="checkbox"
                      checked={state[alert.key] !== false}
                      onChange={async (e) => {
                        try {
                          const updatedState = await updateFeederSettings({ [alert.field]: e.target.checked });
                          setState(updatedState);
                        } catch (error) {
                          console.error(`Failed to update ${alert.key}:`, error);
                        }
                      }}
                      className="w-5 h-5 mr-3 accent-red-500"
                    />
                    <span className="text-lg mr-3">{alert.icon}</span>
                    <span className="text-base font-semibold text-slate-800">{alert.label}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'history' && (
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-white via-slate-50 to-gray-50 p-6 shadow-lg border border-slate-200">
            <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-blue-200/10 to-transparent rounded-full -mr-32 -mt-32"></div>
            <h3 className="text-2xl font-bold text-slate-800 mb-6 flex items-center relative z-10">
              <span className="mr-3 text-3xl">📊</span>
              {t('feedingHistory')}
            </h3>
            <div className="space-y-3 max-h-[600px] overflow-y-auto relative z-10 custom-scrollbar pr-2">
              {feedingHistory.length === 0 ? (
                <div className="text-center py-16">
                  <div className="text-6xl mb-4">📋</div>
                  <div className="text-slate-500 font-medium text-lg">{t('noFeedingHistory')}</div>
                  <div className="text-slate-400 text-sm mt-2">{t('startFeedingToSeeHistory')}</div>
                </div>
              ) : (
                feedingHistory.map((feed, index) => (
                  <div key={index} className="group relative overflow-hidden flex items-center justify-between p-4 bg-white rounded-xl shadow-sm hover:shadow-md border border-slate-200 hover:border-blue-300 transition-all">
                    <div className="absolute inset-0 bg-gradient-to-r from-blue-500/0 to-cyan-500/0 group-hover:from-blue-500/5 group-hover:to-cyan-500/5 transition-all"></div>
                    <div className="flex items-center relative z-10">
                      <div className={`w-12 h-12 rounded-xl mr-4 flex items-center justify-center shadow-md ${feed.feed_type === 'manual' ? 'bg-gradient-to-br from-blue-500 to-blue-600' :
                        feed.feed_type === 'scheduled' ? 'bg-gradient-to-br from-green-500 to-green-600' :
                          feed.feed_type === 'weather_adjusted' ? 'bg-gradient-to-br from-yellow-500 to-amber-600' : 'bg-gradient-to-br from-purple-500 to-purple-600'
                        }`}>
                        <span className="text-white text-xl">
                          {feed.feed_type === 'manual' ? '🕹️' :
                            feed.feed_type === 'scheduled' ? '⏰' :
                              feed.feed_type === 'weather_adjusted' ? '☁️' : '🤖'}
                        </span>
                      </div>
                      <div>
                        <div className="font-bold text-lg text-slate-800">{feed.portion_grams}{t('gFed')}</div>
                        <div className="text-sm text-slate-500 font-medium">
                          {feed.feed_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </div>
                      </div>
                    </div>
                    <div className="text-right relative z-10">
                      <div className="text-sm font-bold text-slate-700">
                        {new Date(feed.timestamp).toLocaleDateString()}
                      </div>
                      <div className="text-xs text-slate-500 font-medium">
                        {new Date(feed.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
