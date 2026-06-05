import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import LanguageToggle from './LanguageToggle'

const Sidebar = () => {
  const location = useLocation()
  const navigate = useNavigate()
  const { t } = useLanguage()

  const menuItems = [
    { path: '/dashboard', labelKey: 'navDashboard', icon: '📊' },
    { path: '/weather', labelKey: 'navWeather', icon: '🌤️' },
    { path: '/feeding', labelKey: 'navFeeding', icon: '🍤' },
    { path: '/reports', labelKey: 'navReports', icon: '📈' },
    { path: '/history', labelKey: 'navHistory', icon: '📋' },
    { path: '/growth-dashboard', label: '🚀 Growth Dashboard', icon: '📈' },
    { path: '/growth-settings', label: '⚙️ Growth Settings', icon: '⚙️' },
    { path: '/alerts', labelKey: 'navAlerts', icon: '⚠️' },
    { path: '/settings', labelKey: 'navSettings', icon: '⚙️' },
    { path: '/about', labelKey: 'navAbout', icon: 'ℹ️' },
  ]

  const handleLogout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    navigate('/login')
  }

  return (
    <div className="w-72 glass-card m-4 rounded-2xl flex flex-col h-[calc(100vh-2rem)] overflow-hidden">
      {/* Header with Shrimp Image Background */}
      <div className="relative p-6 overflow-hidden">
        <div
          className="absolute inset-0 bg-cover bg-center opacity-10"
          style={{ backgroundImage: "url('/shrimp_pond_pic/vannamei-shrimp-Pacific-white-shrimp.avif')" }}
        ></div>
        <div className="absolute inset-0 bg-gradient-to-br from-blue-600/20 to-cyan-600/20"></div>

        <div className="relative z-10">
          <div className="flex items-center mb-4">
            <div className="w-12 h-12 bg-gradient-to-br from-cyan-400 to-blue-500 rounded-xl flex items-center justify-center shadow-lg animate-pulse-glow">
              <span className="text-2xl">🦐</span>
            </div>
            <div className="ml-3">
              <h1 className="text-xl font-bold text-white text-shadow">Smart Shrimp</h1>
              <p className="text-cyan-100 text-sm">{t('aiMonitoring')}</p>
            </div>
          </div>
          <div className="h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent"></div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-6">
        <ul className="space-y-2">
          {menuItems.map((item) => (
            <li key={item.path}>
              <Link
                to={item.path}
                className={`group flex items-center px-4 py-3 rounded-xl transition-all duration-300 ${location.pathname === item.path ||
                  (item.path === '/dashboard' && location.pathname === '/')
                  ? 'bg-gradient-to-r from-cyan-500/20 to-blue-500/20 text-white shadow-lg border border-cyan-400/30'
                  : 'text-slate-300 hover:bg-white/10 hover:text-white hover:translate-x-1'
                  }`}
              >
                <span className="text-xl mr-3 group-hover:scale-110 transition-transform duration-200">{item.icon}</span>
                <span className="font-medium">{item.label || t(item.labelKey)}</span>
                {location.pathname === item.path && (
                  <div className="ml-auto w-2 h-2 bg-cyan-400 rounded-full animate-pulse"></div>
                )}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      {/* Language Toggle */}
      <div className="px-4 pb-2">
        <LanguageToggle />
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-white/10">
        <button
          onClick={handleLogout}
          className="w-full flex items-center px-4 py-3 text-slate-300 hover:bg-red-500/20 hover:text-white rounded-xl transition-all duration-300 group"
        >
          <span className="text-xl mr-3 group-hover:rotate-180 transition-transform duration-300">🚪</span>
          <span className="font-medium">{t('signOut')}</span>
        </button>
      </div>
    </div>
  )
}

export default Sidebar
