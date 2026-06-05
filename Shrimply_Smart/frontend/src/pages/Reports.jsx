import { useState, useEffect, useCallback } from 'react'
import { Line, Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import * as reportsService from '../services/reports'
import { getSensorReadings } from '../services/sensors'
import { fetchHistorySettings } from '../services/historySettings'
import { useLanguage } from '../context/LanguageContext'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

/* ─── small sub-components ─────────────────────────────────────── */
const Toast = ({ message, type, onClose }) => {
  useEffect(() => { const id = setTimeout(onClose, 3500); return () => clearTimeout(id) }, [onClose])
  const bg = type === 'success' ? 'bg-green-500' : type === 'error' ? 'bg-red-500' : 'bg-blue-500'
  return (
    <div className={`fixed top-6 right-6 z-50 ${bg} text-white px-5 py-3 rounded-xl shadow-2xl flex items-center gap-3 animate-slide-in`}>
      <span>{type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
      <span className="text-sm font-medium">{message}</span>
      <button onClick={onClose} className="ml-2 opacity-70 hover:opacity-100">&times;</button>
    </div>
  )
}

const SummaryCard = ({ icon, label, value, unit, min, max, colorClass }) => (
  <div className="glass-card p-5 rounded-2xl">
    <div className="flex items-center gap-2 mb-2 text-slate-600 text-sm">{icon} {label}</div>
    <div className={`text-3xl font-bold ${colorClass}`}>{value}<span className="text-base ml-1 opacity-70">{unit}</span></div>
    {(min !== undefined && max !== undefined) && (
      <div className="text-xs text-slate-500 mt-1">Min {min} — Max {max}</div>
    )}
  </div>
)

/* ─── main component ───────────────────────────────────────────── */
const Reports = () => {
  const { t } = useLanguage()

  /* ── state ─────────────────────────────────────────────────── */
  const [selectedPeriod, setSelectedPeriod] = useState('7days')
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [sensorData, setSensorData] = useState([])
  const [currentPage, setCurrentPage] = useState(1)
  const [sensorTotalCount, setSensorTotalCount] = useState(0)
  const [dateSearch, setDateSearch] = useState('')
  const ITEMS_PER_PAGE = 20

  // Active report (last generated / viewed)
  const [activeReport, setActiveReport] = useState(null)
  // Report history (paginated)
  const [reportHistory, setReportHistory] = useState([])
  const [reportPage, setReportPage] = useState(1)
  const [reportTotalCount, setReportTotalCount] = useState(0)
  const REPORTS_PER_PAGE = 5
  // Custom date range
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')

  // Email modal
  const [emailModal, setEmailModal] = useState({ open: false, reportId: null })
  const [emailAddress, setEmailAddress] = useState('')
  const [emailSending, setEmailSending] = useState(false)

  // Toast
  const [toast, setToast] = useState(null)
  const showToast = useCallback((message, type = 'success') => setToast({ message, type }), [])

  // Chart data & stats from raw sensor
  const [chartData, setChartData] = useState({
    temperature: { labels: [], data: [] },
    ph: { labels: [], data: [] },
    turbidity: { labels: [], data: [] },
    tds: { labels: [], data: [] },
  })
  const [stats, setStats] = useState({
    avgTemp: 0, avgPh: 0, avgTurb: 0, avgTds: 0,
    minTemp: 0, maxTemp: 0, minPh: 0, maxPh: 0,
    minTurb: 0, maxTurb: 0, minTds: 0, maxTds: 0,
    tempChange: 0,
  })

  /* ── init ──────────────────────────────────────────────────── */
  useEffect(() => { setCurrentPage(1); fetchData(1) }, [selectedPeriod])
  useEffect(() => { loadReportHistory(1); loadDefaultEmail() }, [])

  const loadDefaultEmail = async () => {
    try {
      const s = await fetchHistorySettings()
      if (s?.notification_email) setEmailAddress(s.notification_email)
    } catch { /* ignore */ }
  }

  const loadReportHistory = async (page = reportPage) => {
    try {
      const data = await reportsService.getReports(page, REPORTS_PER_PAGE)
      setReportHistory(Array.isArray(data.results) ? data.results : [])
      setReportTotalCount(data.count || 0)
      setReportPage(page)
    } catch (err) { console.error('Failed to load report history', err) }
  }

  /* ── fetch sensor data (server-side paginated) ─────────────── */
  const fetchData = async (page = currentPage) => {
    setLoading(true)
    try {
      const days = parseInt(selectedPeriod.replace('days', '').replace('year', '365'))
      const resp = await getSensorReadings(days || 90, page, ITEMS_PER_PAGE)
      const readings = Array.isArray(resp.results) ? resp.results : []
      setSensorData(readings)
      setSensorTotalCount(resp.count || 0)
      setCurrentPage(page)
      if (readings.length) {
        processChartData(readings)
        calculateStats(readings)
      }
    } catch (error) { console.error('Error fetching sensor data:', error) }
    finally { setLoading(false) }
  }

  const processChartData = (readings) => {
    const subset = readings.slice(0, 20).reverse()
    const labels = subset.map(r => new Date(r.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }))
    setChartData({
      temperature: { labels, data: subset.map(r => parseFloat(r.temperature) || 0) },
      ph: { labels, data: subset.map(r => parseFloat(r.ph) || 0) },
      turbidity: { labels, data: subset.map(r => parseFloat(r.turbidity) || 0) },
      tds: { labels, data: subset.map(r => parseFloat(r.tds) || 0) },
    })
  }

  const calculateStats = (readings) => {
    if (!readings.length) return
    const avg = (arr) => arr.reduce((s, v) => s + v, 0) / arr.length
    const temps = readings.map(r => parseFloat(r.temperature) || 0)
    const phs = readings.map(r => parseFloat(r.ph) || 0)
    const turbidities = readings.map(r => parseFloat(r.turbidity) || 0)
    const tdss = readings.map(r => parseFloat(r.tds) || 0)

    const recent = temps.slice(0, 7)
    const previous = temps.slice(7, 14)
    const tempChange = previous.length ? (avg(recent) - avg(previous)).toFixed(1) : 0

    setStats({
      avgTemp: avg(temps).toFixed(1), minTemp: Math.min(...temps).toFixed(1), maxTemp: Math.max(...temps).toFixed(1),
      avgPh: avg(phs).toFixed(1), minPh: Math.min(...phs).toFixed(1), maxPh: Math.max(...phs).toFixed(1),
      avgTurb: avg(turbidities).toFixed(2), minTurb: Math.min(...turbidities).toFixed(2), maxTurb: Math.max(...turbidities).toFixed(2),
      avgTds: Math.round(avg(tdss)), minTds: Math.round(Math.min(...tdss)), maxTds: Math.round(Math.max(...tdss)),
      tempChange,
    })
  }

  /* ── report generation ─────────────────────────────────────── */
  const handleGenerateReport = async (type) => {
    setGenerating(true)
    try {
      let report
      switch (type) {
        case 'daily': report = await reportsService.generateDailyReport(); break
        case 'weekly': report = await reportsService.generateWeeklyReport(); break
        case 'monthly': report = await reportsService.generateMonthlyReport(); break
        case 'custom':
          if (!customStart || !customEnd) { showToast('Select both start and end dates', 'error'); setGenerating(false); return }
          report = await reportsService.generateCustomReport(customStart, customEnd); break
        default: return
      }
      setActiveReport(report)
      showToast(`${type.charAt(0).toUpperCase() + type.slice(1)} report generated!`)
      loadReportHistory()
    } catch (error) { showToast('Error generating report: ' + error.message, 'error') }
    finally { setGenerating(false) }
  }

  const handleViewReport = async (id) => {
    try {
      const report = await reportsService.getReport(id)
      setActiveReport(report)
      showToast('Report loaded')
    } catch (err) { showToast('Failed to load report', 'error') }
  }

  const handleRegenerateReport = async (id) => {
    setGenerating(true)
    try {
      const report = await reportsService.regenerateReport(id)
      setActiveReport(report)
      showToast('Report regenerated!')
      loadReportHistory()
    } catch (err) { showToast('Regeneration failed', 'error') }
    finally { setGenerating(false) }
  }

  const handleDeleteReport = async (id) => {
    if (!confirm('Delete this report?')) return
    try {
      await reportsService.deleteReport(id)
      if (activeReport?.id === id) setActiveReport(null)
      showToast('Report deleted')
      loadReportHistory()
    } catch (err) { showToast('Failed to delete', 'error') }
  }

  /* ── email ─────────────────────────────────────────────────── */
  const openEmailModal = (reportId) => { setEmailModal({ open: true, reportId }); }
  const closeEmailModal = () => { setEmailModal({ open: false, reportId: null }); setEmailSending(false) }
  const handleSendEmail = async () => {
    if (!emailAddress) { showToast('Enter an email address', 'error'); return }
    setEmailSending(true)
    try {
      await reportsService.emailReport(emailModal.reportId, emailAddress)
      showToast(`Report sent to ${emailAddress}`)
      closeEmailModal()
    } catch (err) { showToast('Failed to send email: ' + err.message, 'error'); setEmailSending(false) }
  }

  /* ── export helpers ────────────────────────────────────────── */
  const handleExportExcel = async () => {
    try {
      const data = sensorData.slice(0, 100).map(r => ({
        date: new Date(r.timestamp).toLocaleDateString(), temperature: r.temperature,
        ph: r.ph, do: r.oxygen, tds: r.tds, status: getStatusFromReading(r),
      }))
      await reportsService.exportToExcel(data, `sensor_data_${selectedPeriod}.xlsx`)
      showToast('Excel exported!')
    } catch (error) { showToast('Export failed: ' + error.message, 'error') }
  }

  const handleGeneratePDF = async () => {
    try {
      const data = sensorData.slice(0, 100).map(r => ({
        date: new Date(r.timestamp).toLocaleDateString(), temperature: r.temperature,
        ph: r.ph, do: r.oxygen, tds: r.tds, status: getStatusFromReading(r),
      }))
      await reportsService.generatePDFReport(data, `Sensor Report - ${selectedPeriod}`)
    } catch (error) { showToast('PDF generation failed: ' + error.message, 'error') }
  }

  /* ── derived: active report data ───────────────────────────── */
  const summary = activeReport?.summary || {}
  const sensorSummary = summary.sensor_data || {}
  const alertSummary = summary.alerts || {}
  const feedingSummary = summary.feeding || {}
  const insights = Array.isArray(activeReport?.insights) ? activeReport.insights : []

  // Use report summary for cards when available, else fall back to sensor stats
  const cardTemp = sensorSummary.temperature || {}
  const cardPh = sensorSummary.ph || {}
  const cardTurb = sensorSummary.turbidity || {}
  const cardTds = sensorSummary.tds || {}

  /* ── alert bar-chart data ──────────────────────────────────── */
  const alertBarData = {
    labels: Object.keys(alertSummary.by_parameter || {}).map(k => k.charAt(0).toUpperCase() + k.slice(1)),
    datasets: [{
      label: 'Alerts',
      data: Object.values(alertSummary.by_parameter || {}),
      backgroundColor: ['rgba(239,68,68,0.7)', 'rgba(34,197,94,0.7)', 'rgba(59,130,246,0.7)', 'rgba(234,179,8,0.7)'],
      borderRadius: 6,
    }],
  }

  /* ── feeding bar-chart data ────────────────────────────────── */
  const feedingBarData = {
    labels: Object.keys(feedingSummary.by_type || {}).map(k => k.replace(/_/g, ' ')),
    datasets: [{
      label: 'Events',
      data: Object.values(feedingSummary.by_type || {}),
      backgroundColor: ['rgba(14,165,233,0.7)', 'rgba(168,85,247,0.7)', 'rgba(249,115,22,0.7)', 'rgba(20,184,166,0.7)'],
      borderRadius: 6,
    }],
  }

  const barOptions = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(0,0,0,0.8)', titleColor: '#fff', bodyColor: '#fff' } },
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#9ca3af' } },
      y: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#9ca3af', stepSize: 1 }, beginAtZero: true },
    },
  }

  /* ── line chart configs ────────────────────────────────────── */
  const makeLineDataset = (label, data, color) => ({
    labels: chartData.temperature.labels,
    datasets: [{
      label,
      data,
      borderColor: color,
      backgroundColor: color.replace('rgb', 'rgba').replace(')', ',0.1)'),
      borderWidth: 2,
      fill: true,
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
      pointBackgroundColor: color,
    }],
  })
  const temperatureData = makeLineDataset('Temperature (°C)', chartData.temperature.data, 'rgb(239,68,68)')
  const phData = makeLineDataset('pH Level', chartData.ph.data, 'rgb(34,197,94)')
  const turbidityData = makeLineDataset('Turbidity (NTU)', chartData.turbidity.data, 'rgb(14,165,233)')
  const tdsData = makeLineDataset('TDS/EC (ppm)', chartData.tds.data, 'rgb(249,115,22)')

  const chartOptions = {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { backgroundColor: 'rgba(0,0,0,0.8)', titleColor: '#fff', bodyColor: '#fff', borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1 } },
    scales: {
      x: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#9ca3af', font: { size: 11 } } },
      y: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: '#9ca3af', font: { size: 11 } } },
    },
    elements: { point: { radius: 3, hoverRadius: 5 }, line: { tension: 0.3 } },
  }
  const temperatureOptions = { ...chartOptions, scales: { ...chartOptions.scales, y: { ...chartOptions.scales.y, min: 25, max: 35 } } }
  const phOptions = { ...chartOptions, scales: { ...chartOptions.scales, y: { ...chartOptions.scales.y, min: 5, max: 9 } } }
  const turbidityOptions = { ...chartOptions, scales: { ...chartOptions.scales, y: { ...chartOptions.scales.y, min: 0, max: 5 } } }
  const tdsOptions = { ...chartOptions, scales: { ...chartOptions.scales, y: { ...chartOptions.scales.y, beginAtZero: false } } }

  /* ── table helpers ─────────────────────────────────────────── */
  const allHistoricalData = sensorData.map(reading => {
    const dt = new Date(reading.timestamp)
    return {
      date: dt.toLocaleDateString(), time: dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      rawDate: dt, temperature: parseFloat(reading.temperature).toFixed(1),
      ph: parseFloat(reading.ph).toFixed(1), turb: parseFloat(reading.turbidity).toFixed(1),
      tds: Math.round(parseFloat(reading.tds)), status: getStatusFromReading(reading),
    }
  })
  // Server-side pagination: sensorData is already the current page.
  // Client-side date filter applies on top of what we have.
  const filteredData = dateSearch
    ? allHistoricalData.filter(row => { const sd = new Date(dateSearch); return row.rawDate.getFullYear() === sd.getFullYear() && row.rawDate.getMonth() === sd.getMonth() && row.rawDate.getDate() === sd.getDate() })
    : allHistoricalData
  const sensorTotalPages = Math.ceil(sensorTotalCount / ITEMS_PER_PAGE)
  // When date search is active we show filtered results directly (within the current server page)
  const historicalData = filteredData

  function getStatusFromReading(reading) {
    const temp = parseFloat(reading.temperature), ph = parseFloat(reading.ph), turb = parseFloat(reading.turbidity)
    const tempOk = temp >= 28 && temp <= 32, phOk = ph >= 7.0 && ph <= 8.5, turbOk = turb >= 0.5 && turb <= 3.0
    if (tempOk && phOk && turbOk) return 'Excellent'
    if (tempOk && phOk) return 'Good'
    if (!tempOk || !phOk || turb > 4.0) return 'Warning'
    return 'Critical'
  }
  const getStatusColor = (s) => ({ Excellent: 'text-green-700 bg-green-100', Good: 'text-blue-700 bg-blue-100', Warning: 'text-yellow-700 bg-yellow-100', Critical: 'text-red-700 bg-red-100' }[s] || 'text-slate-600 bg-slate-100')

  const insightColor = (type) => ({ critical: 'border-red-400 bg-red-50 text-red-700', warning: 'border-yellow-400 bg-yellow-50 text-yellow-700', info: 'border-blue-400 bg-blue-50 text-blue-700' }[type] || 'border-slate-400 bg-slate-50 text-slate-700')
  const insightIcon = (type) => ({ critical: '🔴', warning: '🟡', info: '🔵' }[type] || 'ℹ️')

  /* ─── RENDER ─────────────────────────────────────────────────── */
  return (
    <div className="p-6 space-y-8">
      {/* Toast */}
      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}

      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-slate-800 mb-1">{t('reportsAndAnalytics')}</h1>
        <p className="text-slate-600">{t('reportsSubtitle')}</p>
      </div>

      {/* ═══ Section A: Report Generation ═══ */}
      <div className="glass-card p-6 rounded-2xl space-y-5">
        <h2 className="text-xl font-semibold text-slate-800 flex items-center gap-2">📊 {t('reportPeriod')}</h2>

        {/* Period buttons for sensor chart view */}
        <div className="flex flex-wrap gap-2">
          {[{ value: '7days', label: '7 Days' }, { value: '30days', label: '30 Days' }, { value: '90days', label: '90 Days' }, { value: '1year', label: '1 Year' }].map((p) => (
            <button key={p.value} onClick={() => setSelectedPeriod(p.value)} disabled={loading}
              className={`px-4 py-2 rounded-xl font-medium text-sm transition-all ${selectedPeriod === p.value ? 'bg-cyan-500 text-white shadow-lg shadow-cyan-500/30' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'} ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}>
              {p.label}
            </button>
          ))}
        </div>

        {/* Generate Report buttons */}
        <div className="border-t border-slate-200 pt-4">
          <h3 className="text-sm font-medium text-slate-600 mb-3">{t('quickReportGeneration')}</h3>
          <div className="flex flex-wrap gap-3">
            <button onClick={() => handleGenerateReport('daily')} disabled={generating}
              className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium">
              {generating ? <span className="animate-spin">⏳</span> : '📅'} {t('dailyReport')}
            </button>
            <button onClick={() => handleGenerateReport('weekly')} disabled={generating}
              className="px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium">
              {generating ? <span className="animate-spin">⏳</span> : '📊'} {t('weeklyReport')}
            </button>
            <button onClick={() => handleGenerateReport('monthly')} disabled={generating}
              className="px-4 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium">
              {generating ? <span className="animate-spin">⏳</span> : '📈'} {t('monthlyReport')}
            </button>
          </div>
        </div>

        {/* Custom date range */}
        <div className="border-t border-slate-200 pt-4">
          <h3 className="text-sm font-medium text-slate-600 mb-3">Custom Date Range</h3>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="block text-xs text-slate-600 mb-1">Start Date</label>
              <input type="date" value={customStart} onChange={e => setCustomStart(e.target.value)} className="input-field text-sm px-3 py-2 rounded-xl" />
            </div>
            <div>
              <label className="block text-xs text-slate-600 mb-1">End Date</label>
              <input type="date" value={customEnd} onChange={e => setCustomEnd(e.target.value)} className="input-field text-sm px-3 py-2 rounded-xl" />
            </div>
            <button onClick={() => handleGenerateReport('custom')} disabled={generating || !customStart || !customEnd}
              className="px-4 py-2.5 bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium">
              Generate Custom
            </button>
          </div>
        </div>

        {generating && (
          <div className="flex items-center gap-2 text-cyan-700 text-sm">
            <span className="animate-spin">⏳</span> Generating report…
          </div>
        )}
      </div>

      {/* ═══ Section B: Summary Cards ═══ */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <SummaryCard icon="🌡️" label={t('averageTemperature')} colorClass="text-red-600"
          value={cardTemp.avg ?? stats.avgTemp} unit="°C"
          min={cardTemp.min ?? stats.minTemp} max={cardTemp.max ?? stats.maxTemp} />
        <SummaryCard icon="🧪" label={t('averagePh')} colorClass="text-green-600"
          value={cardPh.avg ?? stats.avgPh} unit=""
          min={cardPh.min ?? stats.minPh} max={cardPh.max ?? stats.maxPh} />
        <SummaryCard icon="🫧" label={t('turbidity')} colorClass="text-blue-600"
          value={cardTurb.avg ?? stats.avgTurb} unit="NTU"
          min={cardTurb.min ?? stats.minTurb} max={cardTurb.max ?? stats.maxTurb} />
        <SummaryCard icon="📏" label={t('averageTds')} colorClass="text-yellow-600"
          value={cardTds.avg ?? stats.avgTds} unit="ppm"
          min={cardTds.min ?? stats.minTds} max={cardTds.max ?? stats.maxTds} />
      </div>

      {/* ═══ Section C: Charts ═══ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('temperatureTrend')}</h3>
          <div className="h-64"><Line data={temperatureData} options={temperatureOptions} /></div>
        </div>
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('phLevelTrend')}</h3>
          <div className="h-64"><Line data={phData} options={phOptions} /></div>
        </div>
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('turbidityTrend')}</h3>
          <div className="h-64"><Line data={turbidityData} options={turbidityOptions} /></div>
        </div>
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('tdsEcTrend')}</h3>
          <div className="h-64"><Line data={tdsData} options={tdsOptions} /></div>
        </div>

        {/* Bar charts — only show when a report is active */}
        {Object.keys(alertSummary.by_parameter || {}).length > 0 && (
          <div className="glass-card p-5 rounded-2xl">
            <h3 className="text-lg font-semibold text-slate-800 mb-4">⚠️ Alerts by Parameter</h3>
            <div className="h-64"><Bar data={alertBarData} options={barOptions} /></div>
            <p className="text-xs text-slate-500 mt-2">{alertSummary.total} total alerts, {alertSummary.unresolved} unresolved</p>
          </div>
        )}
        {Object.keys(feedingSummary.by_type || {}).length > 0 && (
          <div className="glass-card p-5 rounded-2xl">
            <h3 className="text-lg font-semibold text-slate-800 mb-4">🦐 Feeding by Type</h3>
            <div className="h-64"><Bar data={feedingBarData} options={barOptions} /></div>
            <p className="text-xs text-slate-500 mt-2">{feedingSummary.total_events} events, {feedingSummary.total_grams?.toFixed(0)}g total</p>
          </div>
        )}
      </div>

      {/* ═══ Section D: Insights Panel ═══ */}
      {insights.length > 0 && (
        <div className="glass-card p-6 rounded-2xl">
          <h2 className="text-xl font-semibold text-slate-800 mb-4 flex items-center gap-2">💡 Insights</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {insights.map((ins, i) => (
              <div key={i} className={`border rounded-xl p-4 ${insightColor(ins.type)}`}>
                <div className="flex items-start gap-2">
                  <span className="text-lg">{insightIcon(ins.type)}</span>
                  <div>
                    <span className="text-xs font-bold uppercase tracking-wider">{ins.parameter?.replace(/_/g, ' ')}</span>
                    <p className="text-sm mt-0.5 opacity-90">{ins.message}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══ Section E: Sensor Data Table ═══ */}
      <div className="glass-card p-6 rounded-2xl">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h3 className="text-lg font-semibold text-slate-800">{t('historicalReadings')}</h3>
          <div className="flex items-center gap-3">
            <input type="date" value={dateSearch} onChange={(e) => { setDateSearch(e.target.value); setCurrentPage(1) }}
              className="input-field text-sm px-3 py-2 rounded-xl" />
            {dateSearch && (
              <button onClick={() => { setDateSearch(''); setCurrentPage(1) }} className="px-3 py-2 text-sm text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors">
                {t('clear')}
              </button>
            )}
            <span className="text-sm text-slate-500">
              {dateSearch ? `${filteredData.length} ${filteredData.length === 1 ? t('reading') : t('readings')} ${t('found')}` : `${sensorTotalCount} ${t('readings')} ${t('total')}`}
            </span>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{t('temperature')} (°C)</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{t('phLevel')}</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Turbidity (NTU)</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">TDS (ppm)</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{t('status')}</th>
              </tr>
            </thead>
            <tbody>
              {historicalData.length === 0 ? (
                <tr><td colSpan="6" className="px-4 py-8 text-center text-slate-500">{dateSearch ? t('noReadingsFound') : t('noReadingsAvailable')}</td></tr>
              ) : historicalData.map((row, index) => (
                <tr key={index} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 text-sm text-slate-700"><div>{row.date}</div><div className="text-xs text-slate-500">{row.time}</div></td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.temperature}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.ph}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.turbidity}</td>
                  <td className="px-4 py-3 text-sm text-slate-700">{row.tds}</td>
                  <td className="px-4 py-3"><span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusColor(row.status)}`}>{row.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {sensorTotalPages > 1 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-4 py-4 mt-2">
            <div className="text-sm text-slate-600">
              {t('showing')} {((currentPage - 1) * ITEMS_PER_PAGE) + 1}–{Math.min(currentPage * ITEMS_PER_PAGE, sensorTotalCount)} {t('of')} {sensorTotalCount} {t('readings')}
            </div>
            <div className="flex items-center space-x-1">
              <button onClick={() => fetchData(1)} disabled={currentPage === 1}
                className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">««</button>
              <button onClick={() => fetchData(Math.max(currentPage - 1, 1))} disabled={currentPage === 1}
                className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">‹</button>
              {Array.from({ length: sensorTotalPages }, (_, i) => i + 1)
                .filter(page => { if (sensorTotalPages <= 7) return true; if (page === 1 || page === sensorTotalPages) return true; return Math.abs(page - currentPage) <= 1 })
                .reduce((acc, page, idx, arr) => { if (idx > 0 && page - arr[idx - 1] > 1) acc.push('...'); acc.push(page); return acc }, [])
                .map((page, idx) => page === '...'
                  ? <span key={`e-${idx}`} className="px-2 py-1.5 text-sm text-slate-400">…</span>
                  : <button key={page} onClick={() => fetchData(page)}
                    className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${currentPage === page ? 'bg-cyan-600 text-white border-cyan-600' : 'border-slate-300 text-slate-600 hover:bg-slate-100'}`}>{page}</button>
                )}
              <button onClick={() => fetchData(Math.min(currentPage + 1, sensorTotalPages))} disabled={currentPage === sensorTotalPages}
                className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">›</button>
              <button onClick={() => fetchData(sensorTotalPages)} disabled={currentPage === sensorTotalPages}
                className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">»»</button>
            </div>
          </div>
        )}
      </div>

      {/* ═══ Section F: Report History ═══ */}
      <div className="glass-card p-6 rounded-2xl">
        <h2 className="text-xl font-semibold text-slate-800 mb-4 flex items-center gap-2">🗂️ Report History</h2>
        {reportHistory.length === 0 ? (
          <p className="text-slate-500 text-sm">No reports generated yet. Use the buttons above to create one.</p>
        ) : (
          <>
            <div className="space-y-2">
              {reportHistory.map(r => (
                <div key={r.id} className={`flex items-center justify-between p-3 rounded-xl border transition-all ${activeReport?.id === r.id ? 'border-cyan-500/50 bg-cyan-50' : 'border-slate-200 hover:border-slate-300 bg-slate-50'}`}>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-slate-800 truncate">{r.title}</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {r.report_type} &middot; {r.status}
                      {r.generated_at && <> &middot; {new Date(r.generated_at).toLocaleDateString()}</>}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 ml-3 flex-shrink-0">
                    <button onClick={() => handleViewReport(r.id)} title="View"
                      className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors text-sm">👁️</button>
                    <button onClick={() => handleRegenerateReport(r.id)} title="Regenerate" disabled={generating}
                      className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors text-sm disabled:opacity-40">🔄</button>
                    <button onClick={() => openEmailModal(r.id)} title="Email"
                      className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors text-sm">📧</button>
                    <button onClick={() => handleDeleteReport(r.id)} title="Delete"
                      className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors text-sm">🗑️</button>
                  </div>
                </div>
              ))}
            </div>
            {/* Report History Pagination */}
            {(() => {
              const rTotalPages = Math.ceil(reportTotalCount / REPORTS_PER_PAGE); return rTotalPages > 1 ? (
                <div className="flex items-center justify-between border-t border-slate-200 px-2 py-4 mt-3">
                  <div className="text-sm text-slate-600">
                    {((reportPage - 1) * REPORTS_PER_PAGE) + 1}–{Math.min(reportPage * REPORTS_PER_PAGE, reportTotalCount)} of {reportTotalCount} reports
                  </div>
                  <div className="flex items-center space-x-1">
                    <button onClick={() => loadReportHistory(1)} disabled={reportPage === 1}
                      className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">««</button>
                    <button onClick={() => loadReportHistory(Math.max(reportPage - 1, 1))} disabled={reportPage === 1}
                      className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">‹</button>
                    {Array.from({ length: rTotalPages }, (_, i) => i + 1)
                      .filter(p => { if (rTotalPages <= 7) return true; if (p === 1 || p === rTotalPages) return true; return Math.abs(p - reportPage) <= 1 })
                      .reduce((acc, p, idx, arr) => { if (idx > 0 && p - arr[idx - 1] > 1) acc.push('...'); acc.push(p); return acc }, [])
                      .map((p, idx) => p === '...'
                        ? <span key={`re-${idx}`} className="px-2 py-1.5 text-sm text-slate-400">…</span>
                        : <button key={p} onClick={() => loadReportHistory(p)}
                          className={`px-3 py-1.5 text-sm rounded-lg border transition-colors ${reportPage === p ? 'bg-cyan-600 text-white border-cyan-600' : 'border-slate-300 text-slate-600 hover:bg-slate-100'}`}>{p}</button>
                      )}
                    <button onClick={() => loadReportHistory(Math.min(reportPage + 1, rTotalPages))} disabled={reportPage === rTotalPages}
                      className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">›</button>
                    <button onClick={() => loadReportHistory(rTotalPages)} disabled={reportPage === rTotalPages}
                      className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors">»»</button>
                  </div>
                </div>
              ) : null
            })()}
          </>
        )}
      </div>

      {/* ═══ Export Options ═══ */}
      <div className="glass-card p-6 rounded-2xl">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">{t('exportData')}</h3>
        <div className="flex flex-wrap gap-3">
          <button onClick={handleExportExcel} disabled={loading || sensorData.length === 0}
            className="px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium">
            📊 {t('exportToExcel')}
          </button>
          <button onClick={handleGeneratePDF} disabled={loading || sensorData.length === 0}
            className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium">
            📄 {t('generatePDFReport')}
          </button>
          <button onClick={() => { if (activeReport) openEmailModal(activeReport.id); else showToast('Generate a report first', 'error') }}
            disabled={loading}
            className="px-4 py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm font-medium">
            📧 {t('emailReport')}
          </button>
        </div>
      </div>

      {/* ═══ Section G: Email Modal ═══ */}
      {emailModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={closeEmailModal}>
          <div className="glass-card p-6 rounded-2xl w-full max-w-md mx-4 space-y-4" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-slate-800 flex items-center gap-2">📧 Email Report</h3>
            <div>
              <label className="block text-sm text-slate-600 mb-1">Recipient Email</label>
              <input type="email" value={emailAddress} onChange={e => setEmailAddress(e.target.value)}
                placeholder="example@email.com"
                className="input-field w-full px-4 py-2.5 rounded-xl text-sm" />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button onClick={closeEmailModal} className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-sm transition-all">Cancel</button>
              <button onClick={handleSendEmail} disabled={emailSending || !emailAddress}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2">
                {emailSending ? <><span className="animate-spin">⏳</span> Sending…</> : 'Send Report'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Reports
