# 🦐 ML Growth Prediction System - User Guide

## Overview
The Shrimply Smart Growth Prediction System uses machine learning to help you:
- **Track** shrimp population and weight in real-time
- **Predict** growth trends up to 30 days ahead
- **Optimize** feeding based on shrimp size and weather
- **Forecast** exact harvest dates and expected biomass
- **Analyze** survival rates and growth performance

## Getting Started

### 1. Initial Setup

#### Create a New Season
1. Go to **History Overview** page
2. Click **"Start New Season"** button
3. Enter a season name (optional)
4. System automatically records start date

#### Stock Your Pond
1. Navigate to **Growth Dashboard**
2. Select your active season
3. In the left form, enter:
   - **Shrimp Quantity**: Total number of shrimp stocked
   - **Average Weight**: Initial average weight (typically 0.5-1.0g for PL seedlings)
   - **Date**: Stocking date
4. Click **"Save Data & Update Quantity"**

### 2. Daily Data Entry

#### Add Daily Metrics
Every day (or every few days), log your pond's status:

1. **Essential Fields** (minimum):
   - Current shrimp count (if any mortality)
   - Average weight (if growth visible)
   - Date
   
2. **Growth Tracking**:
   - Daily weight gain (grams)
   - Daily mortality rate (%)
   - Feed amount (grams)

3. **Water Quality** (important for predictions):
   - Water temperature (°C)
   - pH level
   - Dissolved oxygen (mg/L)
   - TDS (ppm)
   - Weather condition

4. **Notes**: Any special observations (algae bloom, disease, equipment issues)

#### Example Entry
```
Date: 2024-01-15
Shrimp Count: 48,000 (started 50,000, 4% mortality)
Avg Weight: 3.5g (was 3.2g yesterday)
Daily Gain: 0.3g
Mortality: 0.4%
Feed: 1,200g
Temp: 28.5°C
pH: 7.2
DO: 6.8 mg/L
TDS: 850 ppm
Weather: Clear
Notes: Water change performed, feeding increased
```

### 3. Growth Analytics Dashboard

#### View Current Metrics
The **Quick Stats** section shows:
- **Current Count**: Live shrimp population
- **Avg Weight**: Current average shrimp weight
- **Total Biomass**: Current standing stock (count × avg weight)
- **Stocking Density**: Original density per m²

#### Growth Metrics Tab
**📊 Growth Metrics** shows:
- **Weight Progression**: Line chart of average weight over time
- **Feed & Mortality**: Bar chart comparing feed and mortality rates
- **Population Trend**: Line chart showing shrimp count changes

#### Predictions Tab
**🔮 Predictions** shows:
- **30-Day Forecast**: Weight predictions for the next 30 days
- **Confidence Score**: ML model confidence (decreases with distance)
- **Estimated Harvest Date**: When shrimp reach target weight (18g default)
- **Survival Rate**: Expected survival percentage

#### Recommendations Tab
**💡 Recommendations** shows:
- AI-powered suggestions based on:
  - Current growth rate vs expected
  - Survival rate analysis
  - Weight target milestones
  - Water quality status

### 4. Smart Feeding

#### Calculate Size-Based Adjustment
The system automatically adjusts feed portions based on shrimp size:

```
Shrimp Size  → Feed Adjustment
1g          → 0.5x base portion
5g          → 1.0x base portion (normal)
10g         → 1.3x base portion
15g         → 1.5x base portion
```

#### Use the Feeding Calculator
1. Navigate to **Feeders** management section
2. Click **"Calculate Feeding Adjustment"**
3. Enter current average shrimp weight
4. System returns:
   - Base portion (grams)
   - Size-adjusted amount
   - Weather-adjusted amount (if applicable)
   - Recommended feed type
   - Confidence level

#### Weather-Based Feeding
The system accounts for weather:
- **Rainy**: Reduce portion by 15% (less oxygen)
- **Hot**: Slight reduction (thermal stress)
- **Cold**: Slight reduction (reduced metabolism)

### 5. Interpreting Predictions

#### Growth Rate Analysis
- **Excellent**: >0.3g/day → Increase feed slightly
- **Good**: 0.2-0.3g/day → Maintain current feeding
- **Slow**: <0.2g/day → Increase feed or check water quality
- **Negative**: Weight loss → Emergency: check DO, pH, disease

#### Harvest Estimation
The system calculates harvest date based on:
- Current weight and size
- Observed growth rate
- Target weight (default 18g for market size)
- Predicted survival rate

Example output:
```
Current Weight: 5.2g
Days to Harvest: 42 days (estimated)
Expected Date: 2024-02-26
Expected Count: 47,000 (98% survival)
Total Biomass: 244kg
```

#### Confidence Score
- **90-95%**: Very accurate (recent data, consistent trends)
- **70-90%**: Accurate (good data but recent changes)
- **50-70%**: Use with caution (limited history, unstable)
- **<50%**: Not reliable (too little data)

### 6. Monitoring Water Quality

#### Critical Parameters
| Parameter | Optimal | Alert | Emergency |
|-----------|---------|-------|-----------|
| Temperature | 26-30°C | <24°C or >32°C | <20°C or >35°C |
| pH | 7.0-7.5 | <6.5 or >8.5 | <6.0 or >9.0 |
| DO | >5 mg/L | 3-5 mg/L | <3 mg/L |
| Ammonia | 0 ppm | 0.02-0.05 ppm | >0.1 ppm |

The system factors these into recommendations automatically.

### 7. Performance Metrics

#### Understand Your Analytics
- **Daily Growth Metrics**: Compare day-to-day changes
- **Cumulative Growth**: Total weight gain since start
- **Survival Rate**: Current count vs initial stocking
- **Feed Efficiency**: Total feed ÷ Total weight gain
- **Days Active**: Current culture period

#### Export Reports
From History Overview:
1. Select a season
2. Click **"Export Season Report"** (CSV format)
3. File contains all metrics, averages, and harvests

### 8. Common Scenarios

#### Scenario 1: Sudden Mortality Spike
1. **Action**: Log 10% mortality immediately
2. **Check**: Temperature (too high/low?), pH (out of range?), DO (too low?)
3. **Reduce feeding** until cause is identified
4. **Increase aeration**
5. **Perform water change** (30-50%)
6. Log observations in Notes field

#### Scenario 2: Slow Growth
1. **Check predictions**: Is growth rate declining?
2. **Increase feed** by 20% (if water quality OK)
3. **Check water quality**: Ammonia, TDS levels?
4. **Reduce stocking density** if possible (may not be practical)
5. **Increase aeration**

#### Scenario 3: Harvest Ready
1. **Check predictions**: Date matches forecast?
2. **Verify weights**: Sample 20+ shrimp to confirm
3. **Check survival**: Update shrimp count if different
4. **Plan harvest**: Use estimated biomass for buyers
5. **Log harvest**: Go to History Overview and add Harvest Entry

### 9. Data Entry Best Practices

✅ **DO**:
- Log data consistently (daily or every 2-3 days)
- Measure multiple shrimp and average (don't guess)
- Record water quality regularly
- Note environmental factors (weather, algae, equipment)
- Use precise quantities for better predictions

❌ **DON'T**:
- Skip data entry for weeks
- Use inconsistent measurement methods
- Ignore water quality readings
- Estimate without sampling
- Trust predictions if data is incomplete

### 10. API Reference

#### Update Shrimp Quantity
```bash
PATCH /api/seasons/1/update_shrimp_quantity/
{
  "current_shrimp_quantity": 48000,
  "average_shrimp_weight_grams": 3.5
}
```

#### Add Daily Growth Metric
```bash
POST /api/seasons/1/add_growth_metric/
{
  "date": "2024-01-15",
  "shrimp_count": 48000,
  "avg_weight_grams": 3.5,
  "daily_weight_gain_grams": 0.3,
  "daily_mortality_percent": 0.4,
  "feed_amount_grams": 1200,
  "water_temperature": 28.5,
  "water_ph": 7.2,
  "dissolved_oxygen": 6.8,
  "tds": 850,
  "weather_condition": "clear",
  "notes": "Water change performed"
}
```

#### Get Predictions
```bash
GET /api/seasons/1/growth_predictions/
```

#### Calculate Feed Adjustment
```bash
POST /api/feeders/calculate_feeding_adjustment/
{
  "avg_shrimp_weight_grams": 5.5,
  "include_weather": true
}
```

### 11. Troubleshooting

**Q: Predictions not showing?**
- A: Add at least 7 days of daily metrics data first

**Q: Weight predictions seem wrong?**
- A: Verify data accuracy; 1-2 incorrect entries can throw off ML model

**Q: Confidence score is too low?**
- A: Continue logging data for 2-3 more weeks for better accuracy

**Q: Growth rate declining but no obvious reason?**
- A: Check ammonia and nitrite levels (if available); algae issues?

**Q: Can't update shrimp quantity?**
- A: Ensure season is active; verify you're the season owner

### 12. Advanced Features

#### Feed Type Management
Access predefined feed products optimized for each growth stage:
- **Starter**: 0-1g shrimp (45% protein)
- **Nursery**: 1-3g shrimp (40% protein)
- **Juvenile**: 3-8g shrimp (35% protein)
- **Grower**: 8-15g shrimp (30% protein)
- **Finisher**: 15-20g shrimp (28% protein)

#### ML Model Details
- **Algorithm**: Random Forest (100 trees)
- **Features**: 12 engineered features (feed ratios, moving averages, etc.)
- **Targets**: Weight and population predictions
- **Update**: Automatically retrained daily when new data added

---

## Support & Contact
For issues or questions, contact your system administrator.

**Last Updated**: 2024-01-15
**System Version**: 1.0 (ML Growth Prediction)
