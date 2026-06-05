# 🔌 Frontend Integration Guide

## Quick Setup (5 minutes)

### Step 1: Install Required Packages
```bash
cd frontend
npm install recharts date-fns
```

### Step 2: Add Routes to Your App (App.jsx or Router)

Find your main routing file (likely `src/App.jsx` or `src/Router.jsx`) and add these routes:

```jsx
// Add these imports at the top of your routing file
import GrowthDashboard from './pages/GrowthDashboard';

// Add these routes inside your <Routes> component
<Route path="/growth-dashboard" element={<GrowthDashboard />} />
<Route path="/growth-dashboard/:seasonId" element={<GrowthDashboard />} />
```

### Step 3: Add Navigation Link

Find your navigation menu/sidebar and add:

```jsx
<NavLink to="/growth-dashboard" className="nav-link">
  📈 Growth Dashboard
</NavLink>
```

Or if using a configuration-based navigation:

```js
{
  label: '📈 Growth Dashboard',
  path: '/growth-dashboard',
  icon: 'chart-line',
  description: 'ML growth predictions and analytics'
}
```

### Step 4: Update History Overview (Optional but Recommended)

The HistoryOverview.jsx has already been updated to display:
- Current shrimp quantity
- Average shrimp weight
- Survival rate
- Total biomass

No additional action needed - it will automatically display when data is available!

---

## 🎨 Component Structure

### GrowthDashboard (Main Container)
- **Path**: `src/pages/GrowthDashboard.jsx`
- **Purpose**: Main page combining all growth features
- **Props**: None (uses URL params)
- **Features**:
  - Season selector
  - Quick stats summary
  - Two-column layout
  - Help panel

```jsx
// Usage
<Route path="/growth-dashboard" element={<GrowthDashboard />} />
<Route path="/growth-dashboard/:seasonId" element={<GrowthDashboard />} />
```

### ShrimpQuantityForm (Data Input)
- **Path**: `src/pages/ShrimpQuantityForm.jsx`
- **Purpose**: Input form for daily metrics
- **Props**:
  - `seasonId` (required): Season ID
  - `onUpdate` (optional): Callback after save
- **Features**:
  - Shrimp quantity tracking
  - Water quality parameters
  - Daily growth metrics
  - Auto-submit via API

```jsx
// Usage
import ShrimpQuantityForm from './pages/ShrimpQuantityForm';

<ShrimpQuantityForm
  seasonId={seasonId}
  onUpdate={() => refreshData()}
/>
```

### GrowthAnalytics (Visualization)
- **Path**: `src/pages/GrowthAnalytics.jsx`
- **Purpose**: Display charts and recommendations
- **Props**:
  - `seasonId` (required): Season ID
- **Features**:
  - Growth metrics charts
  - Predictions visualization
  - AI recommendations
  - Tab-based interface

```jsx
// Usage
import GrowthAnalytics from './pages/GrowthAnalytics';

<GrowthAnalytics seasonId={seasonId} />
```

---

## 📱 Styling & Customization

### Color Scheme
The components use Tailwind CSS with this color scheme:

```
Primary Blue:    #3b82f6
Success Green:   #10b981
Warning Orange:  #f59e0b
Danger Red:      #ef4444
Purple:          #8b5cf6
Background:      #0f172a (slate-900)
```

### CSS Classes Used
- `glass-card`: Semi-transparent card with blur effect
- `p-6`: Padding (1.5rem)
- `rounded-lg`: Border radius 8px
- `rounded-2xl`: Border radius 16px
- `text-*-*`: Tailwind text colors

### Responsive Breakpoints
- Mobile: Default (no prefix)
- Tablet: `md:` (768px+)
- Desktop: `lg:` (1024px+)

---

## 🔄 Data Flow

### Creating New Season
```
User Input (History Overview)
    ↓
POST /api/seasons/
    ↓
Season created with is_active=true
    ↓
User navigates to Growth Dashboard
    ↓
Dashboard fetches active season
    ↓
Display season info and forms
```

### Logging Daily Metrics
```
User fills ShrimpQuantityForm
    ↓
Click "Save Data & Update Quantity"
    ↓
PATCH /api/seasons/{id}/update_shrimp_quantity/
    ↓
POST /api/seasons/{id}/add_growth_metric/
    ↓
Data saved to DailyGrowthMetric
    ↓
onUpdate() callback triggers refresh
    ↓
GrowthAnalytics fetches updated data
    ↓
Charts re-render with new data
```

### Generating Predictions
```
(Background) Management command runs:
python manage.py generate_growth_predictions --days-ahead=30
    ↓
Reads last 30 days of DailyGrowthMetric
    ↓
Trains RandomForest model
    ↓
Generates 30 predictions
    ↓
Creates GrowthPrediction records
    ↓
User views in "Predictions" tab
    ↓
GrowthAnalytics fetches and displays
```

---

## 🧪 Testing Locally

### 1. Test Data Entry
```javascript
// In browser console, test the API
const testData = {
  date: "2024-01-15",
  shrimp_count: 50000,
  avg_weight_grams: 3.5,
  daily_weight_gain_grams: 0.25,
  daily_mortality_percent: 0.5,
  feed_amount_grams: 1200
};

// Make API call
fetch('/api/seasons/1/add_growth_metric/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(testData)
})
.then(r => r.json())
.then(console.log);
```

### 2. Test Predictions
```bash
cd backend
python manage.py generate_growth_predictions --season-id=1 --days-ahead=30 --dry-run
```

### 3. Verify Charts
- Navigate to `/growth-dashboard`
- Select a season with data
- Check all three tabs (Metrics, Predictions, Recommendations)
- Verify charts render without errors

---

## 📦 API Service Integration

The components use the existing `api` service from your frontend setup:

```js
// Assumed to be in src/services/api.js
import api from '../services/api';

// Examples of API calls made:
api.get('/api/seasons/')                          // Get all seasons
api.get('/api/seasons/1/')                        // Get season details
api.patch('/api/seasons/1/update_shrimp_quantity/', {...})  // Update quantity
api.post('/api/seasons/1/add_growth_metric/', {...})  // Add daily metric
api.get('/api/seasons/1/growth_metrics/')         // Get metrics list
api.get('/api/seasons/1/growth_predictions/')     // Get predictions list
api.post('/api/feeders/calculate_feeding_adjustment/', {...})  // Feed calc
```

If your API service is at a different path, update the import in each component.

---

## 🚨 Error Handling

### Common Frontend Errors & Fixes

**Error: "recharts not found"**
```bash
npm install recharts
```

**Error: "date-fns not found"**
```bash
npm install date-fns
```

**Error: "API 404 when fetching metrics"**
- Check backend is running
- Verify endpoints are spelled correctly
- Ensure seasonId is valid (get from /api/seasons/)

**Error: "Cannot read property 'results' of undefined"**
- API response format issue
- Check serializers are returning correct format
- Verify data exists before rendering

**Error: "Charts not rendering"**
- Check browser console for errors
- Ensure data array is not empty
- Verify data structure matches expected format

---

## 🔐 Authentication

The components assume:
- User is already authenticated
- API requests include authentication (via api service)
- CORS is properly configured

If authentication fails:
1. Check auth service is working
2. Verify API token is included in headers
3. Ensure backend has CORS headers

---

## 📊 Example Data Format

### Season Object
```json
{
  "id": 1,
  "name": "Season 1",
  "start_date": "2024-01-01",
  "end_date": null,
  "is_active": true,
  "total_harvest_kg": 0,
  "harvest_count": 0,
  "entry_count": 50000,
  "stocking_density": 50000,
  "current_shrimp_quantity": 48000,
  "average_shrimp_weight_grams": 3.5,
  "notes": "",
  "user": 1,
  "days_active": 14,
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-15T08:30:00Z"
}
```

### Daily Growth Metric Object
```json
{
  "id": 1,
  "season": 1,
  "date": "2024-01-15",
  "shrimp_count": 48000,
  "avg_weight_grams": 3.5,
  "daily_weight_gain_grams": 0.25,
  "daily_mortality_percent": 0.4,
  "feed_amount_grams": 1200,
  "water_temperature": 28.5,
  "water_ph": 7.2,
  "dissolved_oxygen": 6.8,
  "tds": 850,
  "weather_condition": "clear",
  "notes": "Water change performed",
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T09:00:00Z"
}
```

### Growth Prediction Object
```json
{
  "id": 1,
  "season": 1,
  "prediction_date": "2024-01-15T09:00:00Z",
  "forecast_date": "2024-01-16",
  "predicted_avg_weight_grams": 3.75,
  "predicted_shrimp_count": 47880,
  "predicted_survival_rate_percent": 99.75,
  "estimated_harvest_date": "2024-02-26",
  "confidence_score": 85,
  "recommendation": "Continue current feeding schedule. Growth rate is optimal.",
  "model_version": "1.0",
  "is_active": true,
  "created_at": "2024-01-15T09:00:00Z"
}
```

---

## 🎯 Feature Checklist

- [ ] Routes added to App.jsx
- [ ] Navigation link added
- [ ] Dependencies installed (recharts, date-fns)
- [ ] Components tested with sample data
- [ ] History Overview displays shrimp quantity
- [ ] Growth Dashboard loads without errors
- [ ] Forms submit successfully
- [ ] Charts render correctly
- [ ] Predictions display (after 7+ days of data)
- [ ] Recommendations appear in tab

---

## 💡 Tips & Best Practices

### Performance
- Use pagination for large metric lists
- Memoize expensive calculations
- Lazy load charts if many seasons

### UX
- Show loading spinner while fetching data
- Display clear error messages
- Provide success feedback after save
- Allow data export/download

### Data Quality
- Validate user input before submit
- Show data confidence indicators
- Highlight anomalies in data
- Provide data entry guidelines

---

## 🔗 Related Documentation

- **User Guide**: [GROWTH_PREDICTION_GUIDE.md](./GROWTH_PREDICTION_GUIDE.md)
- **System Summary**: [SYSTEM_IMPLEMENTATION_SUMMARY.md](./SYSTEM_IMPLEMENTATION_SUMMARY.md)
- **API Reference**: [SYSTEM_IMPLEMENTATION_SUMMARY.md#-api-endpoints](./SYSTEM_IMPLEMENTATION_SUMMARY.md)

---

## ✅ Integration Verification

After completing the above steps, verify:

```
✓ Pages load without errors
✓ Season selector works
✓ Forms submit and save
✓ Charts render with data
✓ Predictions display after 7 days
✓ Recommendations show in tab
✓ Mobile view is responsive
✓ API calls complete successfully
```

---

**Last Updated**: January 2024
**Integration Status**: Ready for production
