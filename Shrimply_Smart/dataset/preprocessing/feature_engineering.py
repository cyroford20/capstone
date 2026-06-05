"""Feature engineering for time-series weather dataset.

Generates lag features, rolling statistics, EWMA, calendar features, holiday flags,
interaction features, and spatial normalization. Saves featured dataset and
feature metadata and scaler for use during training and inference.

Outputs:
- dataset/philippines_weather_featured_v2.csv
- dataset/preprocessing/feature_columns.json
- dataset/preprocessing/feature_scaler_v2.pkl

Run:
    python feature_engineering.py
"""
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import json
from sklearn.preprocessing import StandardScaler
import holidays

ROOT = Path(__file__).resolve().parent.parent
PREP_DIR = ROOT / 'preprocessing'
PREP_DIR.mkdir(exist_ok=True)
RAW_PREPROCESSED = ROOT / 'data' / 'philippines_weather_preprocessed.csv'
OUT_FEATURED = ROOT / 'data' / 'philippines_weather_featured_v2.csv'

LAG_DAYS = 7
ROLL_WINDOWS = [3, 7, 14]
NUMERIC_COLS = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']

PH_HOLIDAYS = holidays.CountryHoliday('PH')


def make_lags(df, cols, lags=LAG_DAYS):
    for col in cols:
        for lag in range(1, lags + 1):
            df[f'{col}_lag_{lag}'] = df.groupby('municipality')[col].shift(lag)
    return df


def make_rolling(df, cols, windows=ROLL_WINDOWS):
    for col in cols:
        for w in windows:
            df[f'{col}_roll_mean_{w}'] = df.groupby('municipality')[col].transform(lambda s: s.shift(1).rolling(window=w, min_periods=1).mean())
            df[f'{col}_roll_std_{w}'] = df.groupby('municipality')[col].transform(lambda s: s.shift(1).rolling(window=w, min_periods=1).std()).fillna(0)
    return df


def make_ewma(df, cols, span=7):
    for col in cols:
        df[f'{col}_ewm_{span}'] = df.groupby('municipality')[col].transform(lambda s: s.shift(1).ewm(span=span, adjust=False).mean())
    return df


def make_calendar(df):
    df['dayofyear'] = df['date'].dt.dayofyear
    df['dayofweek'] = df['date'].dt.dayofweek
    df['is_weekend'] = df['dayofweek'].isin([5,6]).astype(int)
    df['month'] = df['date'].dt.month
    df['is_holiday'] = df['date'].dt.date.apply(lambda d: 1 if d in PH_HOLIDAYS else 0)
    return df


def make_interactions(df):
    # simple interactions
    df['temp_mul_humidity'] = df['temperature'] * df['humidity']
    df['temp_mul_rain'] = df['temperature'] * df['rainfall']
    return df


def spatial_normalize(df):
    # normalize lat/lon to 0-1 range
    if 'latitude' in df.columns and 'longitude' in df.columns:
        lat_min, lat_max = df['latitude'].min(), df['latitude'].max()
        lon_min, lon_max = df['longitude'].min(), df['longitude'].max()
        df['lat_norm'] = (df['latitude'] - lat_min) / (lat_max - lat_min)
        df['lon_norm'] = (df['longitude'] - lon_min) / (lon_max - lon_min)
    return df


def drop_rows_with_na_feature_window(df, required_lags=LAG_DAYS):
    # Drop rows where lag features are missing (cannot be used for supervised training)
    lag_cols = [f'temperature_lag_{i}' for i in range(1, required_lags + 1)]
    existing = [c for c in lag_cols if c in df.columns]
    df = df.dropna(subset=existing)
    return df


def main():
    if not RAW_PREPROCESSED.exists():
        print('Preprocessed file not found:', RAW_PREPROCESSED)
        return
    df = pd.read_csv(RAW_PREPROCESSED, parse_dates=['date'])
    df = df.sort_values(['municipality', 'date']).reset_index(drop=True)

    df = make_lags(df, NUMERIC_COLS)
    df = make_rolling(df, NUMERIC_COLS)
    df = make_ewma(df, NUMERIC_COLS)
    df = make_calendar(df)
    df = make_interactions(df)
    df = spatial_normalize(df)

    # drop rows that lack lag history
    df = drop_rows_with_na_feature_window(df)

    # select feature columns
    feature_cols = [c for c in df.columns if c not in ['country', 'weather_condition', 'condition', 'source']]
    # we'll save numeric feature scaler
    numeric_feature_cols = [c for c in feature_cols if any(c.startswith(p) for p in NUMERIC_COLS) or c in ['lat_norm','lon_norm','dayofyear','month','temp_mul_humidity','temp_mul_rain']]

    scaler = StandardScaler()
    scaler.fit(df[numeric_feature_cols].values)
    joblib.dump(scaler, PREP_DIR / 'feature_scaler_v2.pkl')

    # save feature columns
    with open(PREP_DIR / 'feature_columns.json', 'w') as f:
        json.dump({'feature_columns': feature_cols, 'numeric_columns': numeric_feature_cols}, f, indent=2)

    df.to_csv(OUT_FEATURED, index=False)
    print('Saved featured dataset to', OUT_FEATURED)
    print('Saved feature columns and scaler to', PREP_DIR)

if __name__ == '__main__':
    main()
