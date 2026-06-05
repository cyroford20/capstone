# ✅ Municipality UI Integration - Testing Guide

## 🎉 Integration Complete!

All frontend files have been updated with municipality support. Here's how to test and verify.

---

## 🧪 Testing Steps

### Step 1: Start Your Servers

**Terminal 1 - Django Backend**:
```bash
cd c:\wamp64\www\Shrimply_Smart\Shrimply_Smart
.\.venv\Scripts\Activate.ps1
python manage.py runserver
# Should show: "Starting development server at http://127.0.0.1:8000/"
```

**Terminal 2 - Frontend Dev Server**:
```bash
cd c:\wamp64\www\Shrimply_Smart\Shrimply_Smart\frontend
npm run dev
# Should show: "  ➜  Local:   http://localhost:5173/"
```

---

### Step 2: Open Browser

Navigate to: **http://localhost:5173/weather**

---

### Step 3: Verify Municipality Selector

✅ **Check 1: Selector Appears**
- Look for blue gradient box with "📍 Oriental Mindoro Municipality"
- Should display a dropdown selector
- Should show all 15 municipalities

✅ **Check 2: Calapan City is Default**
- Dropdown should show "Calapan City" selected
- Should display badge "⭐ PRIMARY"
- Should display badge "✓ ML Ready"

✅ **Check 3: Dropdown Works**
- Click dropdown
- Verify you can see all 15 municipalities
- Coastal group (🌊): 8 municipalities
- Inland group (🏞️): 6 municipalities
- Primary group (⭐): Calapan City

---

### Step 4: Test Switching Municipality

✅ **Switch to Puerto Galera**:
1. Select "Puerto Galera" from dropdown
2. Verify:
   - Forecast updates for Puerto Galera
   - ⭐ PRIMARY badge disappears (not primary)
   - 🌊 Coastal badge appears
   - Location in header changes to "Puerto Galera, Oriental Mindoro, Philippines"

✅ **Switch to Pinamalayan**:
1. Select "Pinamalayan" from dropdown
2. Verify:
   - Forecast updates for Pinamalayan
   - 🏞️ Inland badge appears
   - Location updates

✅ **Switch Back to Calapan**:
1. Select "Calapan City" from dropdown
2. Verify:
   - ⭐ PRIMARY and "High-Accuracy Forecast (95%+)" message appear
   - Forecast updates

---

### Step 5: Browser Console Tests

Open browser DevTools (F12) → Console tab

**Test 1: Verify Municipalities Loaded**
```javascript
// Check if municipalities exist in context
const main = document.querySelector('div')
console.log('DOM loaded');

// Can also check network tab for /api/weather/locations/ call
fetch('http://localhost:8000/api/weather/locations/?detailed=true')
  .then(r => r.json())
  .then(d => console.log('Municipalities:', d.municipalities.length)); // Should show 15
```

**Test 2: Get Calapan Forecast**
```javascript
fetch('http://localhost:8000/api/weather/calapan/?days=7&include_confidence=true')
  .then(r => r.json())
  .then(d => console.log('Calapan ML Confidence:', d.ml_confidence)); // Should show > 0.9
```

**Test 3: Get Any Municipality**
```javascript
fetch('http://localhost:8000/api/weather/municipality/?municipality=puerto_galera&days=7')
  .then(r => r.json())
  .then(d => console.log('Puerto Galera Forecast:', d.forecast?.current)); // Should show forecast data
```

---

### Step 6: Responsive Design Test

✅ **Desktop (1920x1080)**:
- Selector looks good
- Badges display properly
- No horizontal scroll

✅ **Tablet (768x1024)**:
- Selector responsive
- Badges stack nicely
- Touch targets clickable

✅ **Mobile (375x812)**:
- Selector full width
- Dropdown usable
- Badges wrapped properly

---

## 🐛 Troubleshooting

### Issue: Selector not appearing
**Solution**:
1. Check browser console for errors (F12)
2. Verify `/api/weather/locations/` endpoint returns data
3. Ensure `MunicipalitySelector.jsx` imported correctly
4. Clear browser cache: Ctrl+Shift+Delete

### Issue: Forecast not updating when switching
**Solution**:
1. Check network tab for API calls
2. Verify `/api/weather/municipality/` endpoint
3. Check browser console for errors
4. Try hard refresh: Ctrl+F5

### Issue: ML Badge not showing
**Solution**:
1. Verify `model_available` field in municipality data
2. Check `/api/weather/locations/?detailed=true`
3. Ensure models exist in backend: `backend/dataset/models/`

### Issue: "High-Accuracy Forecast" message not appearing
**Solution**:
1. Verify `is_primary` field is `true` for Calapan
2. Check network response from `/api/weather/locations/`
3. Verify `selectedMunicipality` state is updating

---

## 📊 Expected Output

### Console Output (After selecting Calapan):
```
GET /api/weather/locations/
Response: 15 municipalities loaded

GET /api/weather/calapan/?days=7
Response: {
  "municipality": "Calapan City",
  "ml_confidence": 0.96,
  "ml_models_active": true,
  "forecast": {...}
}
```

### Visual Elements Expected:
```
┌─────────────────────────────────────┐
│📍 Oriental Mindoro Municipality     │
├─────────────────────────────────────┤
│ [Calapan City ▼]       ⭐ PRIMARY    │
│                         ✓ ML Ready   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│⭐ High-Accuracy Weather Forecast    │
│   Calapan City is optimized for     │
│   95%+ forecast accuracy with ML    │
└─────────────────────────────────────┘
```

---

## ✅ Success Checklist

- [ ] Both servers running (Django on 8000, React on 5173)
- [ ] Weather page loads without errors
- [ ] Municipality selector appears with blue background
- [ ] All 15 municipalities visible in dropdown
- [ ] Calapan City is selected by default
- [ ] ⭐ PRIMARY badge shows for Calapan
- [ ] "High-Accuracy Forecast" message displays
- [ ] Can switch to Puerto Galera
- [ ] Forecast updates when switching
- [ ] 🌊 Coastal badge appears for coastal municipalities
- [ ] 🏞️ Inland badge appears for inland municipalities
- [ ] Switching back to Calapan shows PRIMARY badge again
- [ ] No console errors
- [ ] Responsive on mobile view
- [ ] /api/weather/locations/ returns 15 municipalities
- [ ] /api/weather/calapan/ returns forecast with ml_confidence

---

## 🎯 Files Modified

### Updated Files:
- ✅ `frontend/src/pages/weather/WeatherLayout.jsx`
  - Added municipalities state
  - Load municipalities on mount
  - Handler for municipality change
  - Pass to context

- ✅ `frontend/src/pages/weather/WeatherContext.jsx`
  - Added municipalities, selectedMunicipality, onMunicipalityChange to provider

- ✅ `frontend/src/pages/weather/WeatherHome.jsx`
  - Added import for MunicipalitySelector
  - Added municipalities to context usage
  - Rendered selector with blue gradient section
  - Added PRIMARY focus badge

### New Files:
- ✅ `frontend/src/services/weather/municipalities.js` (service functions)
- ✅ `frontend/src/components/weather/MunicipalitySelector.jsx` (component)

---

## 🚀 Live Demo

After passing all checks, here's what users can do:

1. **Open Weather Page**: See Oriental Mindoro municipalities
2. **See Calapan Featured**: Primary location with 95%+ accuracy target
3. **Switch Municipality**: Click dropdown, pick any of 15
4. **View Forecast**: Get accurate weather for selected municipality
5. **Check Badges**: See coastal/inland, ML status, primary status

---

## 📞 Quick Reference

### API Endpoints Being Used:
- `GET /api/weather/locations/?detailed=true` → List all municipalities
- `POST /api/weather/locations/` → Switch municipality
- `GET /api/weather/calapan/?days=7` → Calapan high-accuracy forecast
- `GET /api/weather/municipality/?municipality={key}` → Any municipality forecast

### Component Props:
- `value` → Current selected municipality object
- `onChange` → Callback when municipality changes
- `disabled` → Disable during loading

### Context Values Available:
- `municipalities` → Array of all 15 municipalities
- `selectedMunicipality` → Current selected municipality object
- `onMunicipalityChange` → Handler function

---

## 🎓 Next Steps

After verification:
1. **Optional**: Add municipality info card (elevation, population, coordinates)
2. **Optional**: Add accuracy metrics display
3. **Optional**: Train location-specific ML models for each municipality
4. **Deploy**: Push to production when ready

---

**Status**: ✅ Ready for Testing  
**Time to Test**: 5-10 minutes  
**Expected Result**: Fully functional municipality selector with 15 options

