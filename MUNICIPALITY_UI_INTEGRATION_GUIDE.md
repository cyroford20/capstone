# 🎯 Oriental Mindoro Municipalities - Weather UI Integration Guide

## Overview

This guide shows how to integrate the 15 Oriental Mindoro municipalities into your weather UI using the new API endpoints and components.

---

## 📦 Files Created

### 1. **Municipality API Service** ✅
**Location**: `frontend/src/services/weather/municipalities.js`

This service provides all API functions for working with municipalities:

```javascript
// Import the service
import {
  fetchMunicipalities,           // Get all 15 municipalities
  setActiveMunicipality,         // Switch to specific municipality
  getCalapanForecast,            // Get Calapan City high-accuracy forecast
  getMunicipalityForecast,       // Get any municipality forecast
  getMunicipalityAccuracyReport, // Get accuracy metrics
  municipalityToLocation,        // Convert to location format
  findNearestMunicipality,       // Find by coordinates
} from './services/weather/municipalities';
```

**Available Functions**:

```javascript
// 1. Fetch all municipalities
const municipalities = await fetchMunicipalities();
// Returns: Array of 15 municipalities with metadata

// 2. Switch active municipality
await setActiveMunicipality('puerto_galera');
// Switches backend to Puerto Galera

// 3. Get Calapan City forecast (HIGH ACCURACY - 95%+)
const forecast = await getCalapanForecast(7); // 7 days
// Returns: Forecast with ML confidence scores

// 4. Get any municipality forecast
const forecast = await getMunicipalityForecast('pinamalayan', 5);
// Returns: Forecast + municipality metadata

// 5. Get accuracy report
const report = await getMunicipalityAccuracyReport('calapan', 'temperature');
// Returns: Accuracy metrics for specific municipality/metric

// 6. Convert municipality to location object
const location = municipalityToLocation(municipality);
// Compatible with existing WeatherLayout system
```

---

### 2. **Municipality Selector Component** ✅
**Location**: `frontend/src/components/weather/MunicipalitySelector.jsx`

Ready-to-use dropdown selector component with:
- ✅ All 15 municipalities
- ✅ Calapan City marked as PRIMARY
- ✅ Grouped by coastal/inland
- ✅ ML status badges
- ✅ Automatic backend switching

**Usage**:

```javascript
import MunicipalitySelector from './components/weather/MunicipalitySelector';

function MyWeatherPage() {
  const [selectedMun, setSelectedMun] = useState(null);

  return (
    <MunicipalitySelector 
      value={selectedMun} 
      onChange={setSelectedMun}
      disabled={false}
    />
  );
}
```

---

## 🚀 Integration Steps

### Step 1: Update WeatherLayout.jsx

**Goal**: Load municipalities on page load and add to state

**File**: `frontend/src/pages/weather/WeatherLayout.jsx`

**Changes**:

1. **Add import at top**:
```javascript
import {
  fetchMunicipalities,
  municipalityToLocation,
} from '../../services/weather/municipalities';
```

2. **Add municipalities state** (around line 30, with other useState):
```javascript
const [municipalities, setMunicipalities] = useState([]);
const [selectedMunicipality, setSelectedMunicipality] = useState(null);
```

3. **Load municipalities on mount** (after the geolocation useEffect):
```javascript
// Load all municipalities on component mount
useEffect(() => {
  const loadMunicipalities = async () => {
    try {
      const data = await fetchMunicipalities();
      setMunicipalities(data);
      
      // Auto-select Calapan City as default
      const calapan = data.find(m => m.is_primary);
      if (calapan) {
        setSelectedMunicipality(calapan);
      }
    } catch (error) {
      console.error('Failed to load municipalities:', error);
    }
  };

  loadMunicipalities();
}, []);
```

4. **Convert municipality to location when selected** (add this method):
```javascript
const handleMunicipalityChange = (municipality) => {
  setSelectedMunicipality(municipality);
  
  // Convert to location format and set as active
  const loc = municipalityToLocation(municipality);
  setLocation(loc);
  
  // Update settings
  const merged = mergeWeatherSettings({ preferredLocation: loc });
  setSettings((s) => ({ ...s, ...merged }));
};
```

5. **Pass municipalities to WeatherContext** (in the provider around line 280-300):
```javascript
<WeatherProvider
  value={{
    forecast,
    air,
    loading,
    error,
    settings,
    location,
    municipalities,           // ADD THIS
    selectedMunicipality,     // ADD THIS
    onMunicipalityChange: handleMunicipalityChange,  // ADD THIS
  }}
>
  <Outlet />
</WeatherProvider>
```

---

### Step 2: Update WeatherContext.jsx

**Goal**: Make municipalities available to all weather components

**File**: `frontend/src/pages/weather/WeatherContext.jsx`

**Add to context**:
```javascript
export const WeatherProvider = ({ children, value }) => {
  return (
    <WeatherContext.Provider
      value={{
        ...value,
        municipalities: value.municipalities || [],        // ADD
        selectedMunicipality: value.selectedMunicipality || null,  // ADD
        onMunicipalityChange: value.onMunicipalityChange || (() => {}),  // ADD
      }}
    >
      {children}
    </WeatherContext.Provider>
  );
};
```

---

### Step 3: Add Municipality Selector to WeatherHome.jsx

**Goal**: Display municipality selector at the top of weather page

**File**: `frontend/src/pages/weather/WeatherHome.jsx`

**Add import**:
```javascript
import MunicipalitySelector from '../../components/weather/MunicipalitySelector';
import { useWeather } from './WeatherContext';
```

**Add to component** (at the top of the return, before alerts):
```javascript
export default function WeatherHome() {
  const { forecast, loading, settings, selectedMunicipality, onMunicipalityChange } = useWeather();

  return (
    <div className="space-y-6">
      {/* MUNICIPALITY SELECTOR SECTION */}
      <div className="bg-gradient-to-r from-blue-50 to-cyan-50 p-6 rounded-2xl border border-blue-200 shadow-sm">
        <h3 className="text-lg font-bold text-gray-900 mb-3">📍 Select Municipality</h3>
        <MunicipalitySelector 
          value={selectedMunicipality}
          onChange={onMunicipalityChange}
          disabled={loading}
        />
      </div>

      {/* PRIMARY FOCUS BADGE (if Calapan) */}
      {selectedMunicipality?.is_primary && (
        <div className="bg-amber-50 border border-amber-300 rounded-2xl p-4 flex items-center gap-3">
          <span className="text-3xl">⭐</span>
          <div>
            <div className="font-bold text-amber-900">High-Accuracy Weather Forecast</div>
            <div className="text-sm text-amber-700">
              Calapan City is optimized for 95%+ forecast accuracy with specialized ML models
            </div>
          </div>
        </div>
      )}

      {/* EXISTING ALERTS & WEATHER CONTENT */}
      {alerts.length > 0 && (
        <div className="space-y-2">
          {/* ... existing alerts code ... */}
        </div>
      )}

      {/* ... rest of existing content ... */}
    </div>
  );
}
```

---

### Step 4: Add Municipality Info Display (Optional)

**Goal**: Show municipality metadata in weather details

**File**: `frontend/src/pages/weather/WeatherDetails.jsx`

**Add component**:
```javascript
export function MunicipalityInfo({ municipality }) {
  if (!municipality) return null;

  return (
    <div className="bg-gray-50 rounded-lg p-4 space-y-2">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-gray-500 font-semibold">FULL NAME</div>
          <div className="font-medium">{municipality.full_name}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 font-semibold">TYPE</div>
          <div className="font-medium">
            {municipality.is_coastal ? '🌊 Coastal' : '🏞️ Inland'}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 font-semibold">ELEVATION</div>
          <div className="font-medium">{municipality.elevation_m} m</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 font-semibold">POPULATION</div>
          <div className="font-medium">
            {(municipality.population_est / 1000).toFixed(0)}K
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 font-semibold">ML MODEL</div>
          <div className={`font-medium ${municipality.model_available ? 'text-green-600' : 'text-gray-600'}`}>
            {municipality.model_available ? '✓ Available' : 'General'}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 font-semibold">COORDINATES</div>
          <div className="font-medium text-sm">
            {municipality.coordinates.latitude.toFixed(4)}°,{' '}
            {municipality.coordinates.longitude.toFixed(4)}°
          </div>
        </div>
      </div>
    </div>
  );
}
```

---

## 📊 Complete Integration Example

Here's a complete example of an updated weather page:

```javascript
import { useEffect, useState } from 'react';
import { useWeather } from './WeatherContext';
import MunicipalitySelector from '../../components/weather/MunicipalitySelector';
import { fetchMunicipalities, municipalityToLocation } from '../../services/weather/municipalities';

export default function WeatherHome() {
  const { forecast, loading, selectedMunicipality, onMunicipalityChange } = useWeather();
  const [municipalities, setMunicipalities] = useState([]);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchMunicipalities();
        setMunicipalities(data);
      } catch (err) {
        console.error('Failed to load municipalities:', err);
      }
    };
    load();
  }, []);

  return (
    <div className="space-y-6">
      {/* Municipality Selector */}
      <div className="bg-gradient-to-r from-blue-50 to-cyan-50 p-6 rounded-2xl border border-blue-200">
        <h3 className="text-lg font-bold mb-3">📍 Oriental Mindoro Municipalities</h3>
        <MunicipalitySelector
          value={selectedMunicipality}
          onChange={onMunicipalityChange}
          disabled={loading}
        />
      </div>

      {/* Primary Focus Badge */}
      {selectedMunicipality?.is_primary && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg p-4">
          <div className="font-bold">⭐ High-Accuracy Forecast (95%+)</div>
          <div className="text-sm text-gray-700">
            Calapan City with specialized ML models
          </div>
        </div>
      )}

      {/* Current Weather */}
      {forecast && !loading && (
        <div className="bg-white rounded-lg p-6 shadow">
          <h2 className="text-2xl font-bold mb-4">
            {forecast.current?.temperature}°{' '}
            {forecast.current?.weather_description}
          </h2>
          {/* ... rest of weather display ... */}
        </div>
      )}

      {loading && <div className="text-center py-8">Loading forecast...</div>}
    </div>
  );
}
```

---

## 🔌 API Endpoints Reference

### 1. Get All Municipalities
```
GET /api/weather/locations/?detailed=true

Response:
{
  "municipalities": [
    {
      "key": "calapan",
      "display_name": "Calapan City",
      "full_name": "Calapan City",
      "coordinates": {"latitude": 13.4138, "longitude": 121.1893},
      "is_primary": true,
      "is_coastal": true,
      "elevation_m": 15,
      "population_est": 79000,
      "model_available": true
    },
    ...
  ]
}
```

### 2. Switch Municipality
```
POST /api/weather/locations/

Request:
{
  "location": "puerto_galera",
  "include_ml_info": true
}

Response:
{
  "success": true,
  "active_location": "puerto_galera",
  "ml_info": {...}
}
```

### 3. Get Calapan Forecast (High Accuracy)
```
GET /api/weather/calapan/?days=7&include_confidence=true

Response:
{
  "municipality": "Calapan City",
  "forecast": {
    "daily": {...},
    "hourly": {...}
  },
  "ml_confidence": 0.96,
  "ml_models_active": true
}
```

### 4. Get Any Municipality Forecast
```
GET /api/weather/municipality/?municipality=puerto_galera&days=7

Response:
{
  "municipality_key": "puerto_galera",
  "municipality_info": {...},
  "forecast": {...},
  "ml_model_available": true
}
```

### 5. Get Accuracy Report
```
GET /api/weather/ml-accuracy/?municipality=calapan&metric=temperature

Response:
{
  "accuracy_report": {
    "calapan": {
      "temperature": {"rmse": 1.2, "accuracy": 96},
      "humidity": {"mae": 7.5, "accuracy": 95},
      ...
    }
  }
}
```

---

## 🎨 UI/UX Recommendations

### Municipality Selector Placement
1. **Top of Weather Page** (Recommended)
   - Makes it prominent
   - Users see municipality options immediately
   - Easy to switch locations

2. **In Sidebar/Navigation**
   - Keeps main content clean
   - Always accessible
   - Shows current selection

3. **As Tab/Section**
   - "Select Location" tab
   - Others: "Dashboard", "Details", "Analytics"

### Visual Indicators
- ⭐ **Primary** = Calapan City (highest accuracy)
- ✓ **ML Ready** = Has dedicated ML model
- 🌊 **Coastal** = Coastal municipality
- 🏞️ **Inland** = Inland municipality

### Badge Display
```
⭐ PRIMARY    ✓ ML Ready    🌊 Coastal    🏞️ Inland
```

---

## 📝 Quick Implementation Checklist

- [ ] Copy `municipalities.js` to `frontend/src/services/weather/`
- [ ] Copy `MunicipalitySelector.jsx` to `frontend/src/components/weather/`
- [ ] Update `WeatherLayout.jsx` with municipalities state + loading logic
- [ ] Update `WeatherContext.jsx` to provide municipalities
- [ ] Update `WeatherHome.jsx` to display municipality selector
- [ ] Test endpoint calls: `http://localhost:8000/api/weather/locations/`
- [ ] Test municipality switching
- [ ] Test Calapan City high-accuracy forecast
- [ ] Test accuracy report

---

## ✅ Testing Guide

### 1. Test Municipality Loading
```javascript
// In browser console
const response = await fetch('http://localhost:8000/api/weather/locations/?detailed=true');
const data = await response.json();
console.log(data.municipalities); // Should show 15 municipalities
```

### 2. Test Municipality Switching
```javascript
const response = await fetch('http://localhost:8000/api/weather/locations/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ location: 'puerto_galera' })
});
const data = await response.json();
console.log(data.active_location); // Should be 'puerto_galera'
```

### 3. Test Calapan Forecast
```javascript
const response = await fetch('http://localhost:8000/api/weather/calapan/?days=7');
const data = await response.json();
console.log(data.ml_confidence); // Should show confidence score
```

### 4. Test Any Municipality
```javascript
const response = await fetch('http://localhost:8000/api/weather/municipality/?municipality=pinamalayan&days=5');
const data = await response.json();
console.log(data.forecast); // Should show forecast data
```

---

## 🐛 Troubleshooting

### Issue: Municipality selector not loading
**Solution**: 
1. Check network tab - is `/api/weather/locations/` being called?
2. Verify backend is running: `python manage.py runserver`
3. Check browser console for errors

### Issue: Forecast not updating when switching municipality
**Solution**:
1. Ensure `onMunicipalityChange` triggers location update
2. Verify location change triggers `useEffect` with location dependency
3. Check if `refresh()` function is being called

### Issue: ML models not available
**Solution**:
1. Check `model_available` flag in municipality data
2. Verify models exist in `backend/dataset/models/`
3. Models follow pattern: `lstm_{municipality}_v3.h5`, `scaler_{municipality}_v3.pkl`

---

## 📚 File Structure

```
frontend/src/
├── components/
│   └── weather/
│       └── MunicipalitySelector.jsx          ✅ NEW
├── services/
│   └── weather/
│       ├── municipalities.js                 ✅ NEW
│       ├── openMeteo.js
│       ├── ensembleForecaster.js
│       └── mlCorrection.js
└── pages/
    └── weather/
        ├── WeatherLayout.jsx                 ✏️ UPDATE
        ├── WeatherContext.jsx                ✏️ UPDATE
        ├── WeatherHome.jsx                   ✏️ UPDATE
        └── WeatherDetails.jsx                ✏️ UPDATE (optional)
```

---

## 🎯 Success Criteria

✅ All 15 municipalities load in dropdown  
✅ Calapan City shows as PRIMARY/default  
✅ Switching municipality updates forecast  
✅ ML badges display correctly  
✅ High-accuracy endpoint works for Calapan  
✅ Coastal/Inland grouping works  
✅ No console errors  
✅ Responsive design on mobile

---

## 🚀 Next Steps

1. **Implement municipality selector** in WeatherHome
2. **Test endpoint calls** with curl/Postman
3. **Add municipality info card** with metadata
4. **Create accuracy dashboard** showing performance by location
5. **Train location-specific ML models** for each municipality
6. **Deploy to production** when ready

---

**Status**: Ready for implementation  
**Difficulty**: Medium (⏱️ 30-45 minutes)  
**Dependencies**: Backend API endpoints ✅ (already deployed)

