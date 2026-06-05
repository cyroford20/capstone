import { authService } from './auth'
import API_BASE from './apiConfig'

// Default to null values when device not available / before first reading
export const DEFAULT_SENSORS = Object.freeze({
  temperature: null,
  ph: null,
  turbidity: null,
  tds: null,
})

export function getDefaultSensors() {
  return JSON.parse(JSON.stringify(DEFAULT_SENSORS))
}

export async function fetchLatestSensors() {
  // Fetch from Django backend API (single data path)
  try {
    const response = await authService.apiCall(`${API_BASE}/sensors/latest/`)
    const data = response?.data ?? (typeof response?.json === 'function' ? await response.json() : response)

    // Validate and normalize response
    const normalized = {
      temperature: data?.temperature ?? null,
      ph: data?.ph ?? null,
      turbidity: data?.turbidity ?? null,
      tds: data?.tds ?? null,
      timestamp: data?.timestamp || null,
    }

    console.log('[API] Latest sensors response:', normalized)
    return normalized
  } catch (error) {
    console.error('[API] Failed to fetch sensors:', error)
    return getDefaultSensors()
  }
}

export function getSensors() {
  return getDefaultSensors()
}

export function saveSensors(values) {
  // No longer saving to localStorage - data is stored in backend
}

export async function updateSensors(data) {
  try {
    const response = await authService.apiCall(`${API_BASE}/update-sensors/`, {
      method: 'POST',
      body: JSON.stringify(data)
    })
    if (response && typeof response.json === 'function') {
      return await response.json()
    }
    return response?.data || {}
  } catch (error) {
    console.error('Failed to update sensors:', error)
    throw error
  }
}

// Get historical sensor readings for charts (supports pagination)
export async function getSensorReadings(days = 7, page = 1, pageSize = 20) {
  try {
    const response = await authService.apiCall(
      `${API_BASE}/sensors/?days=${days}&page=${page}&page_size=${pageSize}`
    )
    const data = response?.data ?? (typeof response?.json === 'function' ? await response.json() : response)
    // Handle DRF paginated response
    if (data && typeof data === 'object' && 'results' in data) {
      return data
    }
    // Legacy non-paginated fallback
    return { count: Array.isArray(data) ? data.length : 0, results: Array.isArray(data) ? data : [], next: null, previous: null }
  } catch (error) {
    console.error('Failed to fetch sensor readings:', error)
    return { count: 0, results: [], next: null, previous: null }
  }
}
