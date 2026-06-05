import { useState, useEffect } from 'react'
import { getThresholds, fetchThresholds } from '../services/settings'
import { fetchLatestSensors, getSensorReadings } from '../services/sensors'
import { getWaterQualityStatus } from '../services/waterQuality'
import { controlBuzzer, playBeeperSound } from '../services/buzzer'
import { fetchActiveAlerts } from '../services/alerts'
import { useNavigate } from 'react-router-dom'
import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import MetricCard from '../components/MetricCard'
import { useLanguage } from '../context/LanguageContext'
import { getChannelsWebSocketUrl } from '../services/apiConfig'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const Dashboard = () => {
  const { t } = useLanguage()
  // Core metric states (read from sensors)
  const [temperature, setTemperature] = useState(null)
  const [phLevel, setPhLevel] = useState(null)
  const [turbidity, setTurbidity] = useState(null)
  const [tds, setTds] = useState(null)
  const [lastSensorTimestamp, setLastSensorTimestamp] = useState(null)
  const [nowTs, setNowTs] = useState(() => Date.now())
  const [thresholds, setThresholds] = useState({})
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [waterQuality, setWaterQuality] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  // Buzzer states
  const [buzzerOn, setBuzzerOn] = useState(false)
  const [activeAlerts, setActiveAlerts] = useState([])
  const [buzzerToggling, setBuzzerToggling] = useState(false)

  const navigate = useNavigate()

  // Manual refresh handler
  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const [sensorsData, thresholdsData, qualityData] = await Promise.all([
        fetchLatestSensors(),
        fetchThresholds(),
        getWaterQualityStatus()
      ])
      setTemperature(sensorsData.temperature ?? null)
      setPhLevel(sensorsData.ph ?? null)
      setTurbidity(sensorsData.turbidity ?? null)
      setTds(sensorsData.tds ?? null)
      setLastSensorTimestamp(sensorsData.timestamp || null)
      setThresholds(thresholdsData)
      setWaterQuality(qualityData)
    } catch (error) {
      console.error('Refresh failed:', error)
    } finally {
      setRefreshing(false)
    }
  }

  // Keep a ticking clock so freshness labels update.
  useEffect(() => {
    const id = setInterval(() => setNowTs(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  // Manual buzzer toggle handler
  const handleBuzzerToggle = async () => {
    setBuzzerToggling(true)
    try {
      const newState = !buzzerOn
      const response = await controlBuzzer(newState)

      if (!response.error) {
        setBuzzerOn(newState)
        playBeeperSound(200, 1000) // Browser beep feedback
      } else {
        console.error('Failed to control buzzer:', response.error)
      }
    } catch (error) {
      console.error('Buzzer toggle failed:', error)
    } finally {
      setBuzzerToggling(false)
    }
  }

  // Fetch initial data from backend
  useEffect(() => {
    const loadData = async () => {
      try {
        console.log('[DASHBOARD] Loading initial sensor data...')
        // Always fetch fresh from API, don't use cached values
        const thresholdsData = await fetchThresholds()
        const [sensorsData, qualityData] = await Promise.all([
          fetchLatestSensors(),
          getWaterQualityStatus()
        ])

        console.log('[DASHBOARD] Sensor data received:', sensorsData)
        console.log('[DASHBOARD] Fresh thresholds:', thresholdsData)

        setTemperature(sensorsData.temperature ?? null)
        setPhLevel(sensorsData.ph ?? null)
        setTurbidity(sensorsData.turbidity ?? null)
        setTds(sensorsData.tds ?? null)
        setLastSensorTimestamp(sensorsData.timestamp || null)
        setThresholds(thresholdsData)
        setWaterQuality(qualityData)
      } catch (error) {
        console.error('Failed to load data:', error)
        // Fallback to defaults
        setThresholds(getThresholds())
      } finally {
        setLoading(false)
      }
    }
    loadData()

    // --- WebSocket for real-time sensor push (with polling fallback) ---
    let ws = null
    let fallbackInterval = null
    let reconnectTimeout = null
    const WS_URL = getChannelsWebSocketUrl('/ws/sensors/')

    const startPollingFallback = () => {
      if (fallbackInterval) return
      console.log('[POLLING] Starting sensor polling fallback every 8s')
      fallbackInterval = setInterval(async () => {
        try {
          const sensorsData = await fetchLatestSensors()
          if (sensorsData.temperature !== null) {
            setTemperature(sensorsData.temperature)
            setPhLevel(sensorsData.ph)
            setTurbidity(sensorsData.turbidity)
            setTds(sensorsData.tds)
            setLastSensorTimestamp(sensorsData.timestamp || null)
            console.log('[POLLING] Updated sensors:', sensorsData)
          }
        } catch (e) {
          console.warn('Sensor poll failed:', e)
        }
      }, 8000)  // Poll every 8 seconds
    }

    const stopPollingFallback = () => {
      if (fallbackInterval) {
        clearInterval(fallbackInterval)
        fallbackInterval = null
      }
    }

    const connectWebSocket = () => {
      try {
        ws = new WebSocket(WS_URL)

        ws.onopen = () => {
          console.log('[WS] Connected to sensor stream')
          stopPollingFallback()
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.temperature !== undefined) setTemperature(data.temperature)
            if (data.ph !== undefined) setPhLevel(data.ph)
            if (data.turbidity !== undefined) setTurbidity(data.turbidity)
            if (data.tds !== undefined) setTds(data.tds)
            if (data.timestamp) setLastSensorTimestamp(data.timestamp)
          } catch (err) {
            console.warn('[WS] Failed to parse message:', err)
          }
        }

        ws.onclose = () => {
          console.warn('[WS] Disconnected — falling back to polling, will retry in 5s')
          startPollingFallback()
          reconnectTimeout = setTimeout(connectWebSocket, 5000)
        }

        ws.onerror = (err) => {
          console.warn('[WS] Error:', err)
          ws.close()
        }
      } catch (err) {
        console.warn('[WS] Could not connect, using polling fallback')
        startPollingFallback()
        reconnectTimeout = setTimeout(connectWebSocket, 5000)
      }
    }

    connectWebSocket()

    return () => {
      stopPollingFallback()
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
      if (ws) ws.close()
    }
  }, [])

  // Reload thresholds when coming back from settings page
  useEffect(() => {
    const handleFocus = async () => {
      const thresholdsData = await fetchThresholds()
      setThresholds(thresholdsData)
    }
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [])

  // Check for active alerts and control buzzer automatically
  useEffect(() => {
    const checkAlerts = async () => {
      try {
        const alerts = await fetchActiveAlerts()
        const alertList = Array.isArray(alerts) ? alerts : (alerts.results || [])
        setActiveAlerts(alertList)

        // Auto-trigger buzzer if there are active alerts
        if (alertList.length > 0 && !buzzerOn) {
          await controlBuzzer(true)
          setBuzzerOn(true)
          playBeeperSound(200, 1000) // Browser beep as fallback
        }
        // Turn off buzzer if no alerts
        else if (alertList.length === 0 && buzzerOn) {
          await controlBuzzer(false)
          setBuzzerOn(false)
        }
      } catch (error) {
        console.error('Failed to check alerts:', error)
      }
    }

    // Check alerts every 5 seconds
    const alertInterval = setInterval(checkAlerts, 5000)
    checkAlerts() // Check immediately on mount

    return () => clearInterval(alertInterval)
  }, [buzzerOn])

  const [chartData, setChartData] = useState({
    temperature: {
      labels: [],
      datasets: [
        {
          label: 'Temperature (°C)',
          data: [],
          borderColor: 'rgb(239, 68, 68)',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: 'rgb(239, 68, 68)',
        },
      ],
    },
    ph: {
      labels: [],
      datasets: [
        {
          label: 'pH Level',
          data: [],
          borderColor: 'rgb(34, 197, 94)',
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: 'rgb(34, 197, 94)',
        },
      ],
    },
    turbidity: {
      labels: [],
      datasets: [
        {
          label: 'Turbidity (NTU)',
          data: [],
          borderColor: 'rgb(14, 165, 233)',
          backgroundColor: 'rgba(14, 165, 233, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: 'rgb(14, 165, 233)',
        },
      ],
    },
    tds: {
      labels: [],
      datasets: [
        {
          label: 'TDS/EC (ppm)',
          data: [],
          borderColor: 'rgb(249, 115, 22)',
          backgroundColor: 'rgba(249, 115, 22, 0.1)',
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: 'rgb(249, 115, 22)',
        },
      ],
    },
  })

  // Load historical sensor readings to populate chart lines
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const resp = await getSensorReadings(1, 1, 50)
        const readings = resp.results || []
        if (readings.length === 0) return

        // Sort by timestamp ascending
        const sorted = [...readings].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))

        const labels = sorted.map(r => {
          const d = new Date(r.timestamp)
          return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
        })
        const temps = sorted.map(r => r.temperature)
        const phs = sorted.map(r => r.ph)
        const turbidities = sorted.map(r => r.turbidity ?? r.tds)
        const tdss = sorted.map(r => r.tds)

        setChartData(prev => ({
          temperature: {
            ...prev.temperature,
            labels: labels.slice(-20),
            datasets: [{ ...prev.temperature.datasets[0], data: temps.slice(-20) }],
          },
          ph: {
            ...prev.ph,
            labels: labels.slice(-20),
            datasets: [{ ...prev.ph.datasets[0], data: phs.slice(-20) }],
          },
          turbidity: {
            ...prev.turbidity,
            labels: labels.slice(-20),
            datasets: [{ ...prev.turbidity.datasets[0], data: turbidities.slice(-20) }],
          },
          tds: {
            ...prev.tds,
            labels: labels.slice(-20),
            datasets: [{ ...prev.tds.datasets[0], data: tdss.slice(-20) }],
          },
        }))
      } catch (err) {
        console.warn('Failed to load sensor history for charts:', err)
      }
    }
    loadHistory()
  }, [])

  // Remove random auto updates; temperature changes only via manual controls
  // Persist sensor values whenever they change so other pages (Alerts) can read them
  // Note: Now using backend storage instead of localStorage

  // On first mount, if there is no stored value for TDS, set it to 300
  // (Removed localStorage check since we use backend now)

  // Update chart data for all metrics
  useEffect(() => {
    const now = new Date()
    const timeLabel = now.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    })
    // Only update charts when we have real sensor values
    if (temperature == null && phLevel == null && turbidity == null && tds == null) {
      return
    }

    setChartData(prev => ({
      temperature: temperature != null ? {
        ...prev.temperature,
        labels: [...prev.temperature.labels, timeLabel].slice(-20),
        datasets: [{
          ...prev.temperature.datasets[0],
          data: [...prev.temperature.datasets[0].data, temperature].slice(-20),
        }],
      } : prev.temperature,
      ph: phLevel != null ? {
        ...prev.ph,
        labels: [...prev.ph.labels, timeLabel].slice(-20),
        datasets: [{
          ...prev.ph.datasets[0],
          data: [...prev.ph.datasets[0].data, phLevel].slice(-20),
        }],
      } : prev.ph,
      turbidity: turbidity != null ? {
        ...prev.turbidity,
        labels: [...prev.turbidity.labels, timeLabel].slice(-20),
        datasets: [{
          ...prev.turbidity.datasets[0],
          data: [...prev.turbidity.datasets[0].data, turbidity].slice(-20),
        }],
      } : prev.turbidity,
      tds: tds != null ? {
        ...prev.tds,
        labels: [...prev.tds.labels, timeLabel].slice(-20),
        datasets: [{
          ...prev.tds.datasets[0],
          data: [...prev.tds.datasets[0].data, tds].slice(-20),
        }],
      } : prev.tds,
    }))
  }, [temperature, phLevel, turbidity, tds])

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: 'rgba(0, 0, 0, 0.8)',
        titleColor: '#fff',
        bodyColor: '#fff',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
      },
    },
    scales: {
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        ticks: {
          color: '#9ca3af',
          font: {
            size: 11,
          },
        },
      },
      y: {
        grid: {
          color: 'rgba(255, 255, 255, 0.1)',
        },
        ticks: {
          color: '#9ca3af',
          font: {
            size: 11,
          },
        },
      },
    },
    elements: {
      point: {
        radius: 3,
        hoverRadius: 5,
      },
      line: {
        tension: 0.3,
      },
    },
  }

  // Metrics configuration — values from sensors, ranges from thresholds
  const metrics = [
    {
      key: 'temperature',
      title: t('temperature'),
      value: temperature,
      unit: '°C',
      icon: '🌡️',
      color: 'danger',
      min: thresholds.temperature?.min || 20,
      max: thresholds.temperature?.max || 35,
      step: 0.1,
      thresholdMin: thresholds.temperature?.min,
      thresholdMax: thresholds.temperature?.max
    },
    {
      key: 'ph',
      title: t('phLevel'),
      value: phLevel,
      unit: '',
      icon: '🧪',
      color: 'success',
      min: thresholds.ph?.min || 3.0,
      max: thresholds.ph?.max || 8.0,
      step: 0.1,
      thresholdMin: thresholds.ph?.min,
      thresholdMax: thresholds.ph?.max
    },
    {
      key: 'turbidity',
      title: t('turbidity'),
      value: turbidity,
      unit: 'NTU',
      icon: '🫧',
      color: 'info',
      min: thresholds.turbidity?.min || 25,
      max: thresholds.turbidity?.max || 50,
      step: 0.1,
      thresholdMin: thresholds.turbidity?.min,
      thresholdMax: thresholds.turbidity?.max
    },
    {
      key: 'tds',
      title: t('tdsEc'),
      value: tds,
      unit: 'ppm',
      icon: '⚡',
      color: 'warning',
      min: thresholds.tds?.min || 100,
      max: thresholds.tds?.max || 160,
      step: 10,
      thresholdMin: thresholds.tds?.min,
      thresholdMax: thresholds.tds?.max
    }
  ]

  // Manual adjustment controls removed — readings come from real sensors now
  // Loading placeholder skeleton to avoid blank screen and unsafe renders
  if (loading) {
    return (
      <div className="p-8 min-h-full bg-gradient-to-br from-slate-50 to-slate-100">
        <h1 className="text-4xl font-bold text-gradient mb-6">{t('dashboard')}</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-40 bg-gray-200 rounded-xl animate-pulse" />
          <div className="h-40 bg-gray-200 rounded-xl animate-pulse" />
          <div className="h-40 bg-gray-200 rounded-xl animate-pulse" />
          <div className="h-40 bg-gray-200 rounded-xl animate-pulse" />
        </div>
      </div>
    )
  }

  const sensorAgeMs = lastSensorTimestamp ? (nowTs - new Date(lastSensorTimestamp).getTime()) : Number.POSITIVE_INFINITY
  const sensorOnline = Number.isFinite(sensorAgeMs) && sensorAgeMs >= 0 && sensorAgeMs <= 20000

  return (
    <div className="p-8 min-h-full bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Hero Header */}
      <div className="mb-8 relative">
        <div className="absolute inset-0 bg-gradient-to-r from-cyan-500/10 to-blue-500/10 rounded-2xl"></div>
        <div className="relative z-10 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold text-gradient mb-2">{t('dashboard')}</h1>
              <p className="text-slate-600 text-lg">{t('dashboardSubtitle')}</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 rounded-xl shadow-sm">
                <div className={`w-3 h-3 rounded-full ${sensorOnline ? 'bg-green-500' : 'bg-red-500'}`} />
                <div className="text-sm font-medium text-slate-700">
                  {sensorOnline ? (t('sensorsOnline') || 'Sensors Online') : (t('sensorsOffline') || 'Sensors Offline')}
                </div>
              </div>
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-xl shadow-sm hover:bg-slate-50 hover:shadow-md transition-all duration-200 text-slate-700 font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                title="Refresh sensor readings"
              >
                <span className={`text-lg ${refreshing ? 'animate-spin' : ''}`}>🔄</span>
                <span className="hidden sm:inline">{refreshing ? t('refreshing') || 'Refreshing...' : t('refresh') || 'Refresh'}</span>
              </button>
              <div className="hidden md:block">
                <div
                  className="w-24 h-24 bg-cover bg-center rounded-2xl shadow-lg animate-float"
                  style={{ backgroundImage: "url('/shrimp_pond_pic/raw-shrimps-on-hand-washing-shrimp-on-bowl-shrimps-background-fresh-shrimp-prawns-for-cooking-seafood-food-in-the-kitchen-free-photo.jpg')" }}
                ></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Water Quality Status Banner */}
      {waterQuality && (
        <div className={`mb-8 p-6 rounded-2xl border-2 shadow-lg ${waterQuality.status === 'good'
          ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-300'
          : 'bg-gradient-to-r from-red-50 to-orange-50 border-red-300'
          }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className={`w-16 h-16 rounded-full flex items-center justify-center text-3xl ${waterQuality.status === 'good' ? 'bg-green-500' : 'bg-red-500'
                }`}>
                {waterQuality.status === 'good' ? '✓' : '⚠'}
              </div>
              <div>
                <h2 className={`text-2xl font-bold ${waterQuality.status === 'good' ? 'text-green-800' : 'text-red-800'
                  }`}>
                  {t('waterQuality')}: {waterQuality.status === 'good' ? t('waterQualityGood') : t('waterQualityPoor')}
                </h2>
                <p className={`text-lg ${waterQuality.status === 'good' ? 'text-green-700' : 'text-red-700'
                  }`}>
                  {waterQuality.message}
                </p>
                {waterQuality.issues && waterQuality.issues.length > 0 && (
                  <div className="mt-2">
                    <p className="text-sm font-semibold text-red-900">{t('issuesDetected')}:</p>
                    <ul className="list-disc list-inside text-sm text-red-800">
                      {waterQuality.issues.map((issue, idx) => (
                        <li key={idx}>{issue}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
            <div className="text-right">
              <div className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-cyan-600 bg-clip-text text-transparent">
                {waterQuality.quality_score?.toFixed(0)}%
              </div>
              <p className="text-sm text-slate-600">{t('qualityScore')}</p>
            </div>
          </div>

          {waterQuality.recommendations && waterQuality.recommendations.length > 0 && (
            <div className="mt-4 p-4 bg-white/50 rounded-lg border border-slate-200">
              <p className="font-semibold text-slate-800 mb-2">🔧 {t('recommendations')}:</p>
              <ul className="space-y-1">
                {waterQuality.recommendations.map((rec, idx) => (
                  <li key={idx} className="text-sm text-slate-700 flex items-start">
                    <span className="mr-2">•</span>
                    <span>{rec}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Metrics Grid */}
      <div className="grid-modern mb-8">
        {metrics.map((metric) => (
          <div key={metric.key} className="relative group">
            <div className="metric-card-modern">
              <div className="flex items-center justify-between mb-4">
                <div className={`p-3 rounded-xl bg-gradient-to-r ${metric.color === 'danger' ? 'from-red-500 to-pink-500' :
                  metric.color === 'success' ? 'from-green-500 to-teal-500' :
                    metric.color === 'warning' ? 'from-yellow-500 to-orange-500' :
                      'from-blue-500 to-cyan-500'
                  } text-white shadow-lg`}>
                  <span className="text-2xl">{metric.icon}</span>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-bold text-slate-800">{metric.value != null ? metric.value : '--'}</div>
                  <div className="text-sm text-slate-500">{metric.value != null ? metric.unit : ''}</div>
                </div>
              </div>

              <div>
                <h3 className="text-lg font-semibold text-slate-800 mb-1">{metric.title}</h3>
                <div className="w-full bg-slate-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all duration-500 ${metric.color === 'danger' ? 'bg-gradient-to-r from-red-500 to-pink-500' :
                      metric.color === 'success' ? 'bg-gradient-to-r from-green-500 to-teal-500' :
                        metric.color === 'warning' ? 'bg-gradient-to-r from-yellow-500 to-orange-500' :
                          'bg-gradient-to-r from-blue-500 to-cyan-500'
                      }`}
                    style={{ width: `${metric.value != null ? ((metric.value / metric.max) * 100) : 0}%` }}
                  ></div>
                </div>
                <div className="flex justify-between text-xs text-slate-500 mt-1">
                  <span>Min: {metric.thresholdMin != null ? metric.thresholdMin : metric.min}</span>
                  <span>Max: {metric.thresholdMax != null ? metric.thresholdMax : metric.max}</span>
                </div>
              </div>
            </div>

            {/* Manual controls removed (read-only view of sensor readings) */}
          </div>
        ))}
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {/* Temperature Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('temperatureTrend')}</h3>
          <div className="h-64">
            <Line data={chartData.temperature} options={chartOptions} />
          </div>
        </div>

        {/* pH Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('phLevelTrend')}</h3>
          <div className="h-64">
            <Line data={chartData.ph} options={chartOptions} />
          </div>
        </div>

        {/* Turbidity Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('turbidityTrend')}</h3>
          <div className="h-64">
            <Line data={chartData.turbidity} options={chartOptions} />
          </div>
        </div>

        {/* TDS/EC Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('tdsEcTrend')}</h3>
          <div className="h-64">
            <Line data={chartData.tds} options={chartOptions} />
          </div>
        </div>
      </div>

      {/* Water Quality Status */}
      <div className="card mb-8">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('waterQualityStatus')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {waterQuality && waterQuality.parameters && (() => {
            const statusItems = [
              { key: 'temperature', label: t('temperature'), icon: '🌡️' },
              { key: 'ph', label: t('phLevel'), icon: '🧪' },
              { key: 'turbidity', label: t('turbidity'), icon: '🫧' },
              { key: 'tds', label: t('tdsEc'), icon: '⚡' }
            ]
            return statusItems.map(item => {
              const param = waterQuality.parameters[item.key]
              if (!param) return null

              const isOptimal = param.status === 'optimal'
              const statusConfig = isOptimal
                ? {
                  bg: 'bg-green-50 border-green-300',
                  text: 'text-green-800',
                  badge: 'bg-green-500 text-white',
                  label: '✓ ' + t('goodForShrimp')
                }
                : {
                  bg: 'bg-red-50 border-red-300',
                  text: 'text-red-800',
                  badge: 'bg-red-500 text-white',
                  label: '✗ ' + t('badForShrimp')
                }

              return (
                <div key={item.key} className={`relative p-4 rounded-lg border-2 shadow-md ${statusConfig.bg}`}>
                  {/* Status Badge */}
                  <div className={`absolute top-2 right-2 px-2 py-1 rounded-full text-xs font-bold ${statusConfig.badge}`}>
                    {isOptimal ? 'GOOD' : 'BAD'}
                  </div>

                  <div className="flex items-center mb-3">
                    <span className="text-3xl mr-3">{item.icon}</span>
                    <div>
                      <h4 className={`font-bold text-sm ${statusConfig.text}`}>{item.label}</h4>
                      <p className="text-xs text-gray-600">
                        {t('optimal')}: {param.min} – {param.max} {param.unit}
                      </p>
                    </div>
                  </div>

                  <div className="text-center py-2">
                    <div className={`text-3xl font-bold ${statusConfig.text}`}>
                      {param.value.toFixed(1)}
                      <span className="text-lg ml-1">{param.unit}</span>
                    </div>
                    <div className={`mt-2 text-xs font-semibold uppercase tracking-wide ${statusConfig.text}`}>
                      {statusConfig.label}
                    </div>
                  </div>

                  {/* Visual indicator bar */}
                  <div className="mt-3 w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${isOptimal ? 'bg-green-500' : 'bg-red-500'}`}
                      style={{
                        width: `${Math.min(100, Math.max(0, ((param.value - param.min) / (param.max - param.min)) * 100))}%`
                      }}
                    ></div>
                  </div>
                </div>
              )
            })
          })()}
        </div>

        {/* Overall Status Summary */}
        {waterQuality && (
          <div className={`mt-6 p-4 rounded-lg border-2 ${waterQuality.status === 'good'
            ? 'bg-green-100 border-green-400'
            : 'bg-red-100 border-red-400'
            }`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <span className="text-4xl mr-4">
                  {waterQuality.status === 'good' ? '✅' : '⚠️'}
                </span>
                <div>
                  <h4 className={`text-xl font-bold ${waterQuality.status === 'good' ? 'text-green-800' : 'text-red-800'
                    }`}>
                    {t('overallWaterQuality')}: {waterQuality.status === 'good' ? t('goodForShrimp') : t('badForShrimp')}
                  </h4>
                  <p className={`text-sm ${waterQuality.status === 'good' ? 'text-green-700' : 'text-red-700'
                    }`}>
                    {waterQuality.message}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <div className={`text-4xl font-bold ${waterQuality.status === 'good' ? 'text-green-700' : 'text-red-700'
                  }`}>
                  {waterQuality.quality_score?.toFixed(0)}%
                </div>
                <p className="text-xs text-gray-600">{t('parametersOptimal')}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('quickActions')}</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            className="btn-primary flex items-center justify-center py-3"
            onClick={() => navigate('/reports')}
          >
            <span className="mr-2">📊</span>
            {t('generateReport')}
          </button>
          <button
            className="btn-secondary flex items-center justify-center py-3"
            onClick={() => navigate('/settings')}
          >
            <span className="mr-2">⚙️</span>
            {t('systemSettings')}
          </button>
          <button
            className="btn-secondary flex items-center justify-center py-3 relative"
            onClick={() => navigate('/alerts')}
          >
            <span className="mr-2">🔔</span>
            {t('viewAlerts')}
            {activeAlerts.length > 0 && (
              <span className="absolute top-1 right-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
                {activeAlerts.length}
              </span>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
