#!/usr/bin/env python3
"""
Generate 500,000 synthetic weather rows for Calapan, Oriental Mindoro, Philippines.

Based on real observed monthly distributions from the existing dataset:
  - Monthly means and standard deviations per parameter
  - Monthly weather condition probabilities
  - Day-to-day autocorrelation (real weather is smooth, not random)
  - Seasonal patterns (rainy Jun-Nov, summer Dec-May)
  - Physical constraints on all variables

Covers dates 2015-01-01 through ~2028-09-30 (≈5,000 days × 100 rows/day = 500,000).
"""

import numpy as np
import pandas as pd
import os, sys
from pathlib import Path

np.random.seed(42)

# ── Monthly climatology for Calapan, Oriental Mindoro ─────────────────
# Derived from real observed data in the existing dataset
MONTHLY = {
    #       temp_mean, temp_std, hum_mean, hum_std, rain_mean, rain_std, wind_mean, wind_std, pres_mean, pres_std
    1:  (26.33, 0.67, 78.67, 4.15,  0.95,  2.36, 15.04, 2.62, 1011.41, 1.20),
    2:  (26.74, 0.76, 77.03, 4.00,  0.54,  1.22, 13.55, 2.29, 1011.41, 1.20),
    3:  (27.95, 0.65, 77.79, 4.03,  0.71,  1.65, 10.09, 2.69, 1010.95, 1.10),
    4:  (29.41, 0.81, 79.82, 3.54,  1.12,  2.70,  9.11, 2.27, 1010.26, 1.10),
    5:  (29.93, 0.75, 81.88, 3.74,  2.20,  4.09,  8.38, 2.19, 1010.44, 1.15),
    6:  (28.99, 0.84, 85.69, 3.68,  6.06, 10.89, 11.42, 2.59, 1010.87, 1.20),
    7:  (28.52, 0.65, 88.19, 3.60,  9.68, 12.37, 11.77, 2.45, 1010.57, 1.25),
    8:  (28.36, 0.79, 90.82, 3.71, 12.14, 17.21, 13.25, 2.33, 1010.77, 1.30),
    9:  (28.01, 0.77, 89.37, 3.79, 13.54, 13.50, 12.44, 2.19, 1010.74, 1.25),
    10: (27.43, 0.74, 86.67, 3.65,  8.11, 11.75, 11.13, 2.55, 1011.19, 1.20),
    11: (26.68, 0.75, 84.80, 4.54,  4.74,  6.96, 11.91, 2.25, 1011.33, 1.15),
    12: (26.24, 0.75, 81.20, 3.85,  1.37,  2.88, 14.12, 2.57, 1011.82, 1.20),
}

# Monthly probability of each weather condition (Cloudy, Rainy, Sunny)
WEATHER_PROBS = {
    1:  (0.119, 0.056, 0.825),
    2:  (0.116, 0.027, 0.857),
    3:  (0.120, 0.039, 0.842),
    4:  (0.107, 0.068, 0.825),
    5:  (0.084, 0.172, 0.744),
    6:  (0.145, 0.327, 0.528),
    7:  (0.088, 0.524, 0.388),
    8:  (0.107, 0.508, 0.385),
    9:  (0.126, 0.627, 0.247),
    10: (0.190, 0.467, 0.344),
    11: (0.107, 0.357, 0.535),
    12: (0.109, 0.080, 0.811),
}

CONDITION_CODES = {0: 'Cloudy', 1: 'Rainy', 2: 'Sunny'}
SEASON_MAP = {1: 'summer', 2: 'summer', 3: 'summer', 4: 'summer', 5: 'summer',
              6: 'rainy', 7: 'rainy', 8: 'rainy', 9: 'rainy', 10: 'rainy',
              11: 'rainy', 12: 'summer'}

TOTAL_ROWS = 500_000

def generate():
    print("[1/4] Computing date range...")
    # ~5000 days covers 2015-01-01 to ~2028-09-16  (13.7 years)
    # 500,000 / 100 rows per day = 5,000 days
    rows_per_day = 100
    n_days = TOTAL_ROWS // rows_per_day  # 5000

    start_date = pd.Timestamp('2015-01-01')
    dates = pd.date_range(start=start_date, periods=n_days, freq='D')

    print(f"    Date range: {dates[0].date()} to {dates[-1].date()} ({n_days} days, {rows_per_day} rows/day)")
    print(f"    Total rows: {n_days * rows_per_day:,}")

    # Pre-allocate arrays
    all_temp = np.empty(TOTAL_ROWS, dtype=np.float64)
    all_hum  = np.empty(TOTAL_ROWS, dtype=np.float64)
    all_rain = np.empty(TOTAL_ROWS, dtype=np.float64)
    all_wind = np.empty(TOTAL_ROWS, dtype=np.float64)
    all_pres = np.empty(TOTAL_ROWS, dtype=np.float64)
    all_cond = np.empty(TOTAL_ROWS, dtype='U6')
    all_cond_enc = np.empty(TOTAL_ROWS, dtype=np.int8)
    all_date = np.empty(TOTAL_ROWS, dtype='datetime64[D]')
    all_year = np.empty(TOTAL_ROWS, dtype=np.int16)
    all_month = np.empty(TOTAL_ROWS, dtype=np.int8)
    all_day = np.empty(TOTAL_ROWS, dtype=np.int8)
    all_season = np.empty(TOTAL_ROWS, dtype='U6')

    print("[2/4] Generating day-level base values with autocorrelation...")
    # Generate smooth daily base values using AR(1) process
    # This makes consecutive days correlated (realistic weather persistence)
    AR_COEFF = 0.85  # high autocorrelation = smooth day-to-day transitions

    day_temp = np.empty(n_days)
    day_hum  = np.empty(n_days)
    day_rain = np.empty(n_days)
    day_wind = np.empty(n_days)
    day_pres = np.empty(n_days)

    # Initialize first day from January statistics
    m0 = MONTHLY[1]
    day_temp[0] = m0[0]
    day_hum[0]  = m0[2]
    day_rain[0] = m0[4]
    day_wind[0] = m0[6]
    day_pres[0] = m0[8]

    for i in range(n_days):
        dt = dates[i]
        month = dt.month
        tm, ts, hm, hs, rm, rs, wm, ws, pm, ps = MONTHLY[month]

        if i == 0:
            day_temp[0] = tm + np.random.normal(0, ts * 0.5)
            day_hum[0]  = hm + np.random.normal(0, hs * 0.5)
            day_rain[0] = max(0, rm + np.random.normal(0, rs * 0.5))
            day_wind[0] = wm + np.random.normal(0, ws * 0.5)
            day_pres[0] = pm + np.random.normal(0, ps * 0.5)
        else:
            # AR(1): value = coeff * previous + (1-coeff) * monthly_mean + noise
            noise_scale = 1 - AR_COEFF**2  # Correct variance scaling
            day_temp[i] = AR_COEFF * day_temp[i-1] + (1 - AR_COEFF) * tm + np.random.normal(0, ts * np.sqrt(noise_scale))
            day_hum[i]  = AR_COEFF * day_hum[i-1]  + (1 - AR_COEFF) * hm + np.random.normal(0, hs * np.sqrt(noise_scale))
            day_rain[i] = AR_COEFF * day_rain[i-1] + (1 - AR_COEFF) * rm + np.random.normal(0, rs * np.sqrt(noise_scale))
            day_wind[i] = AR_COEFF * day_wind[i-1] + (1 - AR_COEFF) * wm + np.random.normal(0, ws * np.sqrt(noise_scale))
            day_pres[i] = AR_COEFF * day_pres[i-1] + (1 - AR_COEFF) * pm + np.random.normal(0, ps * np.sqrt(noise_scale))

    # Clamp daily values to physical limits
    day_temp = np.clip(day_temp, 23.5, 33.0)
    day_hum  = np.clip(day_hum, 60.0, 100.0)
    day_rain = np.clip(day_rain, 0.0, 100.0)
    day_wind = np.clip(day_wind, 2.0, 25.0)
    day_pres = np.clip(day_pres, 1003.0, 1017.0)

    print("[3/4] Expanding to per-row values with intra-day variation...")
    idx = 0
    for i in range(n_days):
        dt = dates[i]
        month = dt.month
        tm, ts, hm, hs, rm, rs, wm, ws, pm, ps = MONTHLY[month]

        # Intra-day noise (much smaller than daily variation)
        temps = day_temp[i] + np.random.normal(0, ts * 0.3, rows_per_day)
        hums  = day_hum[i]  + np.random.normal(0, hs * 0.3, rows_per_day)
        rains = day_rain[i] + np.random.normal(0, rs * 0.15, rows_per_day)
        winds = day_wind[i] + np.random.normal(0, ws * 0.3, rows_per_day)
        press = day_pres[i] + np.random.normal(0, ps * 0.3, rows_per_day)

        # Clamp
        temps = np.clip(temps, 23.5, 33.0)
        hums  = np.clip(hums, 60.0, 100.0)
        rains = np.clip(rains, 0.0, 100.0)
        winds = np.clip(winds, 2.0, 25.0)
        press = np.clip(press, 1003.0, 1017.0)

        # Round to match original data precision
        temps = np.round(temps, 2)
        hums  = np.round(hums, 2)
        rains = np.round(rains, 3)
        winds = np.round(winds, 2)
        press = np.round(press, 2)

        # Weather condition for this day
        cp, rp, sp = WEATHER_PROBS[month]
        # Adjust probabilities based on rainfall
        if day_rain[i] > 5:
            rp_adj = min(0.85, rp + 0.3)
            sp_adj = max(0.05, sp - 0.25)
            cp_adj = max(0.05, 1 - rp_adj - sp_adj)
        elif day_rain[i] < 0.5:
            sp_adj = min(0.95, sp + 0.2)
            rp_adj = max(0.02, rp - 0.15)
            cp_adj = max(0.03, 1 - sp_adj - rp_adj)
        else:
            cp_adj, rp_adj, sp_adj = cp, rp, sp

        # Normalize
        total = cp_adj + rp_adj + sp_adj
        probs = np.array([cp_adj, rp_adj, sp_adj]) / total

        cond_code = np.random.choice([0, 1, 2], p=probs)
        cond_name = CONDITION_CODES[cond_code]
        season = SEASON_MAP[month]

        # Consistency: if rainy condition but very little rain, bump rain up
        if cond_name == 'Rainy':
            rains = np.clip(rains, 0.5, 100.0)
        elif cond_name == 'Sunny':
            # Sunny days tend to have less rain
            rains = rains * 0.3
            rains = np.round(np.clip(rains, 0.0, 10.0), 3)

        slc = slice(idx, idx + rows_per_day)
        all_temp[slc] = temps
        all_hum[slc]  = hums
        all_rain[slc] = rains
        all_wind[slc] = winds
        all_pres[slc] = press
        all_cond[slc] = cond_name
        all_cond_enc[slc] = cond_code
        all_date[slc] = np.datetime64(dt.date())
        all_year[slc] = dt.year
        all_month[slc] = dt.month
        all_day[slc] = dt.day
        all_season[slc] = season
        idx += rows_per_day

        if (i + 1) % 1000 == 0:
            print(f"    {i+1}/{n_days} days generated ({idx:,} rows)...")

    print(f"    Total: {idx:,} rows generated")

    print("[4/4] Building DataFrame and saving CSV...")
    df = pd.DataFrame({
        'date': pd.to_datetime(all_date),
        'country': 'Philippines',
        'province': 'Oriental Mindoro',
        'municipality': 'Calapan',
        'temperature': all_temp,
        'humidity': all_hum,
        'rainfall': all_rain,
        'wind_speed': all_wind,
        'pressure': all_pres,
        'weather_condition': all_cond,
        'year': all_year,
        'month': all_month,
        'day': all_day,
        'season': all_season,
        'weather_condition_encoded': all_cond_enc,
    })

    # Format date column to match original
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')

    out_path = Path(__file__).resolve().parent.parent / 'data' / 'calapan_500k.csv'
    df.to_csv(out_path, index=False)
    print(f"\n[DONE] Saved {len(df):,} rows to {out_path}")
    print(f"       File size: {out_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Quick sanity check
    print("\n=== Sanity Check ===")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Temp: {df['temperature'].mean():.2f} ± {df['temperature'].std():.2f}")
    print(f"Humidity: {df['humidity'].mean():.2f} ± {df['humidity'].std():.2f}")
    print(f"Rainfall: {df['rainfall'].mean():.2f} ± {df['rainfall'].std():.2f}")
    print(f"Wind: {df['wind_speed'].mean():.2f} ± {df['wind_speed'].std():.2f}")
    print(f"Pressure: {df['pressure'].mean():.2f} ± {df['pressure'].std():.2f}")
    print(f"Conditions: {df['weather_condition'].value_counts().to_dict()}")

    return df

if __name__ == '__main__':
    generate()
