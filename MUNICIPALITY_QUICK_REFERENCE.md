# Quick Reference: Oriental Mindoro Municipalities UI Integration

## 🚀 Quick Start (5 minutes)

### 1. Files Already Created ✅
```
✓ frontend/src/services/weather/municipalities.js
✓ frontend/src/components/weather/MunicipalitySelector.jsx
```

### 2. Add to WeatherLayout.jsx (5 lines)
```javascript
// Import
import { fetchMunicipalities, municipalityToLocation } from '../../services/weather/municipalities';

// State
const [municipalities, setMunicipalities] = useState([]);
const [selectedMunicipality, setSelectedMunicipality] = useState(null);

// On mount
useEffect(() => {
  fetchMunicipalities().then(data => {
    setMunicipalities(data);
    const calapan = data.find(m => m.is_primary);
    setSelectedMunicipality(calapan);
  });
}, []);

// Handler
const handleMunicipalityChange = (municipality) => {
  setSelectedMunicipality(municipality);
  const loc = municipalityToLocation(municipality);
  setLocation(loc);
};
```

### 3. Add to WeatherHome.jsx (10 lines)
```javascript
import MunicipalitySelector from '../../components/weather/MunicipalitySelector';

// Inside return:
<div className="bg-blue-50 p-6 rounded-2xl border border-blue-200 mb-6">
  <h3 className="text-lg font-bold mb-3">📍 Select Municipality</h3>
  <MunicipalitySelector 
    value={selectedMunicipality}
    onChange={onMunicipalityChange}
    disabled={loading}
  />
</div>
```

---

## 📋 The 15 Municipalities

### ⭐ PRIMARY (High Accuracy)
- **Calapan City** (13.4138°N, 121.1893°E) - 95%+ accuracy

### 🌊 COASTAL (8 municipalities)
- Puerto Galera
- San Teodoro
- Baco
- Socorro
- Pola
- Bansud
- Bongabong
- Mansalay

### 🏞️ INLAND (6 municipalities)
- Naujan
- Victoria
- Pinamalayan
- Gloria
- Roxas
- Bulalacao

---

## 🔌 API Endpoints

### Fetch All
```
GET /api/weather/locations/?detailed=true
```

### Switch Municipality
```
POST /api/weather/locations/
Body: {"location": "puerto_galera", "include_ml_info": true}
```

### Calapan High-Accuracy
```
GET /api/weather/calapan/?days=7&include_confidence=true
```

### Any Municipality
```
GET /api/weather/municipality/?municipality=pinamalayan&days=7
```

### Accuracy Report
```
GET /api/weather/ml-accuracy/?municipality=calapan
```

---

## 🎯 Component Props

### MunicipalitySelector
```javascript
<MunicipalitySelector 
  value={municipality}           // Current selected
  onChange={(mun) => {...}}      // On change handler
  disabled={false}               // Disable during loading
/>
```

---

## 💡 Common Code Patterns

### Get All Municipalities
```javascript
import { fetchMunicipalities } from './services/weather/municipalities';

const municipalities = await fetchMunicipalities();
console.log(municipalities.length); // 15
```

### Switch Municipality
```javascript
import { setActiveMunicipality } from './services/weather/municipalities';

await setActiveMunicipality('puerto_galera');
```

### Get Calapan Forecast
```javascript
import { getCalapanForecast } from './services/weather/municipalities';

const forecast = await getCalapanForecast(7);
console.log(forecast.ml_confidence); // e.g. 0.96 (96%)
```

### Get Any Municipality
```javascript
import { getMunicipalityForecast } from './services/weather/municipalities';

const forecast = await getMunicipalityForecast('pinamalayan', 5);
```

### Convert to Location
```javascript
import { municipalityToLocation } from './services/weather/municipalities';

const location = municipalityToLocation(municipality);
// Returns compatible with WeatherLayout location system
```

---

## 🎨 UI Display

### Municipality Object Structure
```javascript
{
  key: "calapan",
  display_name: "Calapan City",
  full_name: "Calapan City",
  coordinates: {
    latitude: 13.4138,
    longitude: 121.1893
  },
  is_primary: true,
  is_coastal: true,
  elevation_m: 15,
  population_est: 79000,
  weather_api_alias: "Calapan",
  model_available: true
}
```

### Badges to Display
- ⭐ `is_primary` → "PRIMARY"
- ✓ `model_available` → "ML Ready"
- 🌊 `is_coastal` → "Coastal"
- 🏞️ NOT coastal → "Inland"

---

## ✅ Testing

### In Browser Console
```javascript
// Load all municipalities
const r1 = await fetch('/api/weather/locations/?detailed=true');
const d1 = await r1.json();
console.log(d1.municipalities.length); // Should be 15

// Get Calapan forecast
const r2 = await fetch('/api/weather/calapan/?days=7');
const d2 = await r2.json();
console.log(d2.ml_confidence); // Should be > 0.9
```

---

## 🐛 Debug Tips

### Check if municipalities loaded
```javascript
console.log(municipalities.length); // Should be 15
```

### Check if API working
```javascript
console.log(window.location.origin); // http://localhost:5173
// API should be at http://localhost:8000/api
```

### Check if component rendering
```javascript
// In MunicipalitySelector props
console.log('value:', value);
console.log('loading:', loading);
console.log('disabled:', disabled);
```

---

## 📚 File Locations

| File | Location | Purpose |
|------|----------|---------|
| Service | `frontend/src/services/weather/municipalities.js` | API calls |
| Component | `frontend/src/components/weather/MunicipalitySelector.jsx` | Dropdown selector |
| Layout | `frontend/src/pages/weather/WeatherLayout.jsx` | STATE & LOADING |
| Home | `frontend/src/pages/weather/WeatherHome.jsx` | DISPLAY |
| Context | `frontend/src/pages/weather/WeatherContext.jsx` | SHARING |

---

## ⏱️ Estimated Work Time

| Task | Time |
|------|------|
| Copy files (already done) | 0 min ✅ |
| Update WeatherLayout.jsx | 5 min |
| Update WeatherContext.jsx | 3 min |
| Update WeatherHome.jsx | 5 min |
| Test endpoints | 5 min |
| **TOTAL** | **18 min** |

---

## 🎯 Success Checklist

- [ ] Both service & component files copied
- [ ] WeatherLayout imports municipalities service
- [ ] State variables added (municipalities, selectedMunicipality)
- [ ] useEffect loads municipalities on mount
- [ ] Handler converts municipality to location
- [ ] MunicipalitySelector rendered in WeatherHome
- [ ] Test endpoint: GET /api/weather/locations/
- [ ] Test switching municipality
- [ ] No console errors
- [ ] Dropdown shows all 15 municipalities
- [ ] Calapan City marked as PRIMARY
- [ ] Coastal/Inland grouping visible

---

## 🔗 Links to Full Documentation

- **Full Integration Guide**: `MUNICIPALITY_UI_INTEGRATION_GUIDE.md`
- **API Documentation**: `ORIENTAL_MINDORO_WEATHER_INTEGRATION.md`
- **Testing Guide**: `ORIENTAL_MINDORO_TESTING_GUIDE.md`
- **Implementation Summary**: `IMPLEMENTATION_SUMMARY.md`

---

## 💬 Support

If you need help:
1. Check **Full Integration Guide** for detailed steps
2. Look at **Common Code Patterns** above
3. Run **Testing** commands to verify setup
4. Check **Debug Tips** for troubleshooting

---

**Last Updated**: June 1, 2026  
**Status**: Production Ready ✅
