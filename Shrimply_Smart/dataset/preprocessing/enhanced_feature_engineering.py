"""
Enhanced Feature Engineering for Weather Prediction — v3
=========================================================
Implements ALL accuracy improvements:
1. Lag features (1-7 days) with rolling stats
2. Seasonal decomposition (NE/SW monsoon patterns)
3. Geospatial features (coast distance, elevation, lat/lon)
4. Temporal features (day of year, monsoon cycle, lunar phase)
5. ENSO indices (El Niño / La Niña proxy)
6. Interaction & polynomial features
7. Philippines-specific typhoon/monsoon signals

Run:
    python enhanced_feature_engineering.py

Outputs:
    dataset/data/philippines_weather_featured_v3.csv
    dataset/preprocessing/feature_columns_v3.json
    dataset/preprocessing/feature_scaler_v3.pkl
"""
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import json
import math
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
PREP_DIR = ROOT / 'preprocessing'
PREP_DIR.mkdir(exist_ok=True)
RAW_PATH = ROOT / 'data' / 'philippines_weather_raw.csv'
PREPROCESSED_PATH = ROOT / 'data' / 'philippines_weather_preprocessed.csv'
OUT_FEATURED = ROOT / 'data' / 'philippines_weather_featured_v3.csv'

NUMERIC_COLS = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
LAG_DAYS = [1, 2, 3, 5, 7]
ROLL_WINDOWS = [3, 7, 14]
EWM_SPANS = [7, 14]

# ── Geospatial data for Philippine municipalities ──────────────────────────
# lat, lon, elevation_m, distance_to_coast_km (approximate)
MUNICIPALITY_GEO = {
    'Urdaneta':    {'lat': 15.976, 'lon': 120.571, 'elev':  56, 'coast_km': 35},
    'Dagupan':     {'lat': 16.043, 'lon': 120.340, 'elev':   2, 'coast_km':  1},
    'San Carlos':  {'lat': 15.928, 'lon': 120.347, 'elev':   3, 'coast_km':  2},
    'Calapan':     {'lat': 13.411, 'lon': 121.180, 'elev':   7, 'coast_km':  1},
    'Pinamalayan': {'lat': 13.015, 'lon': 121.478, 'elev':  15, 'coast_km':  2},
    'Roxas':       {'lat': 12.626, 'lon': 121.507, 'elev':  10, 'coast_km':  3},
    'Santa Cruz':  {'lat': 13.221, 'lon': 121.407, 'elev':  30, 'coast_km':  8},
    'Bacolod':     {'lat': 10.676, 'lon': 122.950, 'elev':  10, 'coast_km':  1},
    'Silay':       {'lat': 10.812, 'lon': 122.969, 'elev':  20, 'coast_km':  3},
    'Talisay':     {'lat': 10.741, 'lon': 122.966, 'elev':  12, 'coast_km':  1},
    'Cebu City':   {'lat': 10.315, 'lon': 123.885, 'elev':  25, 'coast_km':  1},
    'Lapu-Lapu':   {'lat': 10.311, 'lon': 123.949, 'elev':   5, 'coast_km':  0.5},
    'Mandaue':     {'lat': 10.324, 'lon': 123.922, 'elev':  10, 'coast_km':  1},
    'Davao City':  {'lat':  7.073, 'lon': 125.612, 'elev':  20, 'coast_km':  5},
    'Digos':       {'lat':  6.749, 'lon': 125.357, 'elev':  12, 'coast_km': 10},
}

# ── 1. Lag features ───────────────────────────────────────────────────────
def add_lag_features(df):
    """Add lag features: previous 1-7 day values per municipality."""
    df = df.sort_values(['municipality', 'date']).reset_index(drop=True)
    for col in NUMERIC_COLS:
        for lag in LAG_DAYS:
            df[f'{col}_lag{lag}'] = df.groupby('municipality')[col].shift(lag)
        # Lag averages
        df[f'{col}_lag3_avg'] = df.groupby('municipality')[col].transform(
            lambda s: s.shift(1).rolling(3, min_periods=1).mean())
        df[f'{col}_lag7_avg'] = df.groupby('municipality')[col].transform(
            lambda s: s.shift(1).rolling(7, min_periods=1).mean())
    return df


# ── 2. Rolling statistics ─────────────────────────────────────────────────
def add_rolling_features(df):
    """Add rolling mean, std, max, min for multiple windows."""
    for col in NUMERIC_COLS:
        for w in ROLL_WINDOWS:
            grp = df.groupby('municipality')[col]
            df[f'{col}_roll_mean_{w}'] = grp.transform(
                lambda s: s.shift(1).rolling(w, min_periods=1).mean())
            df[f'{col}_roll_std_{w}'] = grp.transform(
                lambda s: s.shift(1).rolling(w, min_periods=1).std()).fillna(0)
            df[f'{col}_roll_max_{w}'] = grp.transform(
                lambda s: s.shift(1).rolling(w, min_periods=1).max())
            df[f'{col}_roll_min_{w}'] = grp.transform(
                lambda s: s.shift(1).rolling(w, min_periods=1).min())
        # Diff features (rate of change)
        df[f'{col}_diff1'] = df.groupby('municipality')[col].diff(1)
        df[f'{col}_diff3'] = df.groupby('municipality')[col].diff(3)
    return df


# ── 3. Exponential weighted moving average ────────────────────────────────
def add_ewm_features(df):
    """Add EWMA for capturing recent trends."""
    for col in NUMERIC_COLS:
        for span in EWM_SPANS:
            df[f'{col}_ewm{span}'] = df.groupby('municipality')[col].transform(
                lambda s: s.shift(1).ewm(span=span, adjust=False).mean())
    return df


# ── 4. Cyclical temporal features ─────────────────────────────────────────
def add_temporal_features(df):
    """Add cyclical date encoding + monsoon cycle day."""
    df['dayofyear'] = df['date'].dt.dayofyear
    df['day_sin'] = np.sin(2 * np.pi * df['dayofyear'] / 365)
    df['day_cos'] = np.cos(2 * np.pi * df['dayofyear'] / 365)

    df['month_num'] = df['date'].dt.month
    df['month_sin'] = np.sin(2 * np.pi * df['month_num'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month_num'] / 12)

    week_of_year = df['date'].dt.isocalendar().week.astype(int)
    df['week_sin'] = np.sin(2 * np.pi * week_of_year / 52)
    df['week_cos'] = np.cos(2 * np.pi * week_of_year / 52)

    df['dayofweek'] = df['date'].dt.dayofweek

    # Monsoon cycle day: day within current monsoon season
    # SW monsoon (Habagat) Jun 1 → Oct 31 (≈153 days)
    # NE monsoon (Amihan) Nov 1 → May 31 (≈212 days)
    def monsoon_cycle_day(row):
        month, doy = row['month_num'], row['dayofyear']
        if 6 <= month <= 10:
            # SW monsoon: day 152 (Jun 1) is start
            start = 152
            return max(0, doy - start)
        else:
            # NE monsoon: day 305 (Nov 1) is start, wraps around year
            if month >= 11:
                return doy - 305
            else:
                return doy + 60  # approx days since Nov 1
    df['monsoon_cycle_day'] = df.apply(monsoon_cycle_day, axis=1)
    return df


# ── 5. Lunar phase (affects rainfall patterns) ────────────────────────────
def lunar_phase(date):
    """Approximate lunar phase (0–29.53 day cycle). 0=new, ~15=full."""
    # Known new moon: Jan 6, 2000
    ref = pd.Timestamp('2000-01-06')
    days_since = (date - ref).days
    return days_since % 29.53

def add_lunar_features(df):
    """Add lunar cycle features (sin/cos for cyclical encoding)."""
    phase = df['date'].apply(lunar_phase)
    df['lunar_phase'] = phase
    df['lunar_sin'] = np.sin(2 * np.pi * phase / 29.53)
    df['lunar_cos'] = np.cos(2 * np.pi * phase / 29.53)
    return df


# ── 6. Seasonal / Monsoon flags ──────────────────────────────────────────
def add_seasonal_flags(df):
    """Add Philippine seasonal indicators."""
    m = df['month_num']
    df['is_wet_season'] = m.isin([6, 7, 8, 9, 10, 11]).astype(int)
    df['is_dry_season'] = 1 - df['is_wet_season']
    df['is_habagat'] = m.isin([6, 7, 8, 9]).astype(int)       # SW monsoon
    df['is_amihan'] = m.isin([10, 11, 12, 1, 2, 3]).astype(int)  # NE monsoon
    df['is_typhoon_season'] = m.isin([6, 7, 8, 9, 10, 11]).astype(int)
    df['is_typhoon_peak'] = m.isin([8, 9, 10]).astype(int)
    df['is_hot_dry'] = m.isin([3, 4, 5]).astype(int)            # Tag-init
    # Transition periods (monsoon onset/withdrawal)
    df['is_monsoon_transition'] = m.isin([5, 6, 10, 11]).astype(int)
    return df


# ── 7. Geospatial features ───────────────────────────────────────────────
def add_geospatial_features(df):
    """Add elevation, coast distance, normalized lat/lon."""
    geo_df = pd.DataFrame.from_dict(MUNICIPALITY_GEO, orient='index')
    geo_df.index.name = 'municipality'
    geo_df = geo_df.reset_index()

    df = df.merge(geo_df, on='municipality', how='left')

    # Normalize lat/lon to 0-1
    if 'lat' in df.columns:
        df['lat_norm'] = (df['lat'] - df['lat'].min()) / (df['lat'].max() - df['lat'].min() + 1e-8)
        df['lon_norm'] = (df['lon'] - df['lon'].min()) / (df['lon'].max() - df['lon'].min() + 1e-8)
        # Log-transform coast distance (diminishing effect)
        df['coast_km_log'] = np.log1p(df['coast_km'])
        # Elevation normalized
        df['elev_norm'] = df['elev'] / (df['elev'].max() + 1e-8)
    return df


# ── 8. ENSO proxy features ───────────────────────────────────────────────
def add_enso_proxy(df):
    """Add El Niño / La Niña seasonal proxy based on historical patterns.
    
    In production, you'd fetch the actual ONI (Oceanic Niño Index) data.
    Here we use a simple seasonal approximation based on known ENSO events:
    - 2023-2024: El Niño event
    - 2022: La Niña event (tail end)
    """
    def enso_index(date):
        y, m = date.year, date.month
        # Known approximate ONI values (simplified)
        if y == 2022:
            return -0.8 if m <= 8 else -0.5  # La Niña
        elif y == 2023:
            if m <= 4:
                return 0.0   # Neutral
            elif m <= 8:
                return 0.8   # El Niño developing
            else:
                return 1.5   # Strong El Niño
        elif y == 2024:
            if m <= 4:
                return 1.2   # El Niño continuing
            elif m <= 8:
                return 0.3   # Transition to neutral
            else:
                return -0.3  # Weak La Niña
        elif y == 2025:
            if m <= 4:
                return -0.5  # La Niña
            elif m <= 8:
                return 0.0   # Neutral
            else:
                return 0.3   # Neutral/weak El Niño
        else:
            return 0.0  # Neutral default

    df['enso_index'] = df['date'].apply(enso_index)
    # El Niño = warmer/drier, La Niña = wetter/cooler
    df['is_el_nino'] = (df['enso_index'] > 0.5).astype(int)
    df['is_la_nina'] = (df['enso_index'] < -0.5).astype(int)
    return df


# ── 9. Interaction & derived features ────────────────────────────────────
def add_interaction_features(df):
    """Add interaction, polynomial, and derived weather features."""
    # Dew point approximation (Magnus formula simplified)
    df['dew_point'] = df['temperature'] - ((100 - df['humidity']) / 5)

    # Heat index approximation (Steadman, simplified)
    T = df['temperature']
    H = df['humidity']
    df['heat_index'] = -8.785 + 1.611*T + 2.339*H - 0.146*T*H - 0.0126*(T**2) - 0.0164*(H**2) + 0.0022*(T**2)*H + 0.0007*T*(H**2) - 0.0000036*(T**2)*(H**2)

    # Wind chill effect (minimal in tropics but useful as feature)
    df['wind_chill'] = 13.12 + 0.6215*T - 11.37*(df['wind_speed']**0.16) + 0.3965*T*(df['wind_speed']**0.16)

    # Interaction terms
    df['temp_x_humidity'] = df['temperature'] * df['humidity']
    df['temp_x_rain'] = df['temperature'] * df['rainfall']
    df['pressure_x_wind'] = df['pressure'] * df['wind_speed']
    df['humidity_x_rain'] = df['humidity'] * df['rainfall']
    df['wind_x_rain'] = df['wind_speed'] * df['rainfall']

    # Quadratic terms
    df['humidity_sq'] = df['humidity'] ** 2
    df['pressure_sq'] = df['pressure'] ** 2

    # Pressure change signals (weather front indicators)
    df['pressure_drop_1d'] = df.groupby('municipality')['pressure'].diff(1)
    df['pressure_drop_3d'] = df.groupby('municipality')['pressure'].diff(3)
    df['humidity_rise_1d'] = df.groupby('municipality')['humidity'].diff(1)

    # Rain persistence (consecutive rain days)
    df['rain_yesterday'] = (df.groupby('municipality')['rainfall'].shift(1) > 0.1).astype(int)
    df['rain_3day_sum'] = df.groupby('municipality')['rainfall'].transform(
        lambda s: s.shift(1).rolling(3, min_periods=1).sum())
    df['rain_7day_sum'] = df.groupby('municipality')['rainfall'].transform(
        lambda s: s.shift(1).rolling(7, min_periods=1).sum())

    # Temperature anomaly (deviation from location mean)
    df['temp_anomaly'] = df['temperature'] - df.groupby('municipality')['temperature'].transform('mean')
    df['humidity_anomaly'] = df['humidity'] - df.groupby('municipality')['humidity'].transform('mean')
    df['pressure_anomaly'] = df['pressure'] - df.groupby('municipality')['pressure'].transform('mean')

    return df


# ── 10. Weather extreme indicators ───────────────────────────────────────
def add_extreme_indicators(df):
    """Add flags for extreme weather conditions."""
    df['is_hot'] = (df['temperature'] > 33).astype(int)
    df['is_cold'] = (df['temperature'] < 22).astype(int)
    df['is_heavy_rain'] = (df['rainfall'] > 20).astype(int)
    df['is_very_heavy_rain'] = (df['rainfall'] > 50).astype(int)
    df['is_high_wind'] = (df['wind_speed'] > 30).astype(int)
    df['is_storm_wind'] = (df['wind_speed'] > 60).astype(int)
    df['is_low_pressure'] = (df['pressure'] < 1005).astype(int)
    df['is_very_low_pressure'] = (df['pressure'] < 995).astype(int)
    # Compound extreme: typhoon-like conditions
    df['is_typhoon_conditions'] = (
        (df['wind_speed'] > 40) & 
        (df['rainfall'] > 30) & 
        (df['pressure'] < 1005)
    ).astype(int)
    return df


# ── 11. Historical same-day-of-year averages ─────────────────────────────
def add_historical_averages(df):
    """Add historical averages for same day-of-year per municipality."""
    df['month_day'] = df['date'].dt.strftime('%m-%d')
    hist = df.groupby(['municipality', 'month_day']).agg({
        'temperature': 'mean',
        'humidity': 'mean',
        'rainfall': 'mean',
        'wind_speed': 'mean',
        'pressure': 'mean',
    }).reset_index()
    hist.columns = ['municipality', 'month_day',
                     'hist_temp_mean', 'hist_humidity_mean', 'hist_rain_mean',
                     'hist_wind_mean', 'hist_pressure_mean']
    df = df.merge(hist, on=['municipality', 'month_day'], how='left')
    # Deviation from historical
    df['temp_vs_hist'] = df['temperature'] - df['hist_temp_mean']
    df['humidity_vs_hist'] = df['humidity'] - df['hist_humidity_mean']
    df['rain_vs_hist'] = df['rainfall'] - df['hist_rain_mean']
    df.drop(columns=['month_day'], inplace=True)
    return df


# ═══════════════════════════════════════════════════════════════════════════
def main():
    print("=" * 70)
    print("  Enhanced Feature Engineering v3 — Philippines Weather Dataset")
    print("=" * 70)

    # Prefer preprocessed data; fall back to raw
    if PREPROCESSED_PATH.exists():
        df = pd.read_csv(PREPROCESSED_PATH, parse_dates=['date'])
        print(f"[OK] Loaded preprocessed data: {len(df)} rows")
    elif RAW_PATH.exists():
        df = pd.read_csv(RAW_PATH, parse_dates=['date'])
        print(f"[OK] Loaded raw data: {len(df)} rows")
    else:
        print("[ERROR] No data file found!")
        return

    df = df.sort_values(['municipality', 'date']).reset_index(drop=True)
    initial = len(df)

    # Apply all feature engineering steps
    print("[1/11] Adding lag features...")
    df = add_lag_features(df)

    print("[2/11] Adding rolling statistics...")
    df = add_rolling_features(df)

    print("[3/11] Adding EWMA features...")
    df = add_ewm_features(df)

    print("[4/11] Adding temporal features...")
    df = add_temporal_features(df)

    print("[5/11] Adding lunar phase features...")
    df = add_lunar_features(df)

    print("[6/11] Adding seasonal/monsoon flags...")
    df = add_seasonal_flags(df)

    print("[7/11] Adding geospatial features...")
    df = add_geospatial_features(df)

    print("[8/11] Adding ENSO proxy features...")
    df = add_enso_proxy(df)

    print("[9/11] Adding interaction features...")
    df = add_interaction_features(df)

    print("[10/11] Adding extreme indicators...")
    df = add_extreme_indicators(df)

    print("[11/11] Adding historical averages...")
    df = add_historical_averages(df)

    # Drop rows with NaN from lag/rolling operations
    df = df.dropna().reset_index(drop=True)
    dropped = initial - len(df)
    print(f"[OK] Dropped {dropped} rows with missing lag values → {len(df)} rows remain")

    # Identify feature columns (exclude metadata)
    exclude_cols = {'date', 'country', 'province', 'municipality',
                    'weather_condition', 'condition', 'source', 'season'}
    feature_cols = [c for c in df.columns if c not in exclude_cols and df[c].dtype in ['float64', 'int64', 'int32', 'float32']]
    numeric_feature_cols = feature_cols.copy()

    # Fit and save scaler
    scaler = StandardScaler()
    scaler.fit(df[numeric_feature_cols].values)
    joblib.dump(scaler, PREP_DIR / 'feature_scaler_v3.pkl')

    # Save feature columns metadata
    meta = {
        'feature_columns': feature_cols,
        'numeric_columns': numeric_feature_cols,
        'total_features': len(feature_cols),
        'total_rows': len(df),
        'version': 'v3',
        'enhancements': [
            'lag_1_2_3_5_7',
            'rolling_3_7_14_with_max_min',
            'ewm_7_14',
            'cyclical_temporal',
            'lunar_phase',
            'monsoon_flags',
            'geospatial_elev_coast',
            'enso_proxy',
            'interaction_polynomial',
            'extreme_indicators',
            'historical_averages',
        ]
    }
    with open(PREP_DIR / 'feature_columns_v3.json', 'w') as f:
        json.dump(meta, f, indent=2)

    df.to_csv(OUT_FEATURED, index=False)
    print(f"\n{'=' * 70}")
    print(f"  Saved: {OUT_FEATURED}")
    print(f"  Features: {len(feature_cols)}")
    print(f"  Rows: {len(df)}")
    print(f"  Metadata: {PREP_DIR / 'feature_columns_v3.json'}")
    print(f"  Scaler: {PREP_DIR / 'feature_scaler_v3.pkl'}")
    print(f"{'=' * 70}")

if __name__ == '__main__':
    main()
