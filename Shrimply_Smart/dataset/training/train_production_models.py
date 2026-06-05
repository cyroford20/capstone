#!/usr/bin/env python3
"""
Train production weather models using the merged 883K dataset
(383K original + 500K Calapan-focused) for maximum accuracy on
Oriental Mindoro / Calapan predictions.

Produces:
  - XGBoost v3 models per target (temperature, humidity, rainfall, wind_speed, pressure)
  - Quantile models for confidence intervals
  - Feature lists and model metrics
  - Correction models (OpenWeather → local accuracy)
  - Condition classifier + encoder
  - last_data.pkl for fallback predictions

All models saved to dataset/models/ for use by EnhancedWeatherPredictor.
"""

import os, sys, json, warnings, time
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor

warnings.filterwarnings('ignore')

# ── Paths ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
MODELS_DIR = BASE_DIR / 'models'
MODELS_DIR.mkdir(exist_ok=True)

MERGED_CSV = DATA_DIR / 'philippines_weather_merged.csv'
TARGETS = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']

# Normalization ranges (must match EnhancedWeatherPredictor.norm_ranges)
NORM_RANGES = {
    'temperature': (20, 38),
    'humidity': (40, 100),
    'rainfall': (0, 150),
    'wind_speed': (0, 60),
    'pressure': (990, 1030),
}


def normalize(col, val):
    lo, hi = NORM_RANGES[col]
    return np.clip((val - lo) / (hi - lo), 0, 1)


def denormalize(col, val):
    lo, hi = NORM_RANGES[col]
    return val * (hi - lo) + lo


# ── Feature Engineering ───────────────────────────────────────────────

# Geospatial data per municipality (must match predictor)
GEO = {
    'Urdaneta':    {'lat': 15.976, 'lon': 120.571, 'elev': 56,  'coast_km': 35},
    'Dagupan':     {'lat': 16.043, 'lon': 120.340, 'elev': 2,   'coast_km': 1},
    'San Carlos':  {'lat': 15.928, 'lon': 120.347, 'elev': 3,   'coast_km': 2},
    'Calapan':     {'lat': 13.411, 'lon': 121.180, 'elev': 7,   'coast_km': 1},
    'Pinamalayan': {'lat': 13.015, 'lon': 121.478, 'elev': 15,  'coast_km': 2},
    'Roxas':       {'lat': 12.626, 'lon': 121.507, 'elev': 10,  'coast_km': 3},
    'Santa Cruz':  {'lat': 13.221, 'lon': 121.407, 'elev': 30,  'coast_km': 8},
    'Bacolod':     {'lat': 10.676, 'lon': 122.950, 'elev': 10,  'coast_km': 1},
    'Silay':       {'lat': 10.812, 'lon': 122.969, 'elev': 20,  'coast_km': 3},
    'Talisay':     {'lat': 10.741, 'lon': 122.966, 'elev': 12,  'coast_km': 1},
    'Cebu City':   {'lat': 10.315, 'lon': 123.885, 'elev': 25,  'coast_km': 1},
    'Lapu-Lapu':   {'lat': 10.311, 'lon': 123.949, 'elev': 5,   'coast_km': 0.5},
    'Mandaue':     {'lat': 10.324, 'lon': 123.922, 'elev': 10,  'coast_km': 1},
    'Davao City':  {'lat': 7.073,  'lon': 125.612, 'elev': 20,  'coast_km': 5},
    'Digos':       {'lat': 6.749,  'lon': 125.357, 'elev': 12,  'coast_km': 10},
}

ENSO = {2015: 2.3, 2016: -0.7, 2017: -0.9, 2018: 0.8, 2019: 0.3,
        2020: -1.3, 2021: -0.9, 2022: 0.3, 2023: -0.5, 2024: 0.8,
        2025: -0.3, 2026: -0.1, 2027: 0.0, 2028: 0.0}


def build_features(df):
    """Engineer all features expected by EnhancedWeatherPredictor v3."""
    print("[FEAT] Engineering features...")
    t0 = time.time()

    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df.sort_values(['municipality', 'date'], inplace=True)

    # Group to daily means (per municipality)
    daily = df.groupby(['municipality', 'date']).agg({
        'temperature': 'mean', 'humidity': 'mean', 'rainfall': 'mean',
        'wind_speed': 'mean', 'pressure': 'mean',
        'weather_condition': lambda x: x.mode().iloc[0] if not x.mode().empty else 'Sunny',
        'weather_condition_encoded': 'first',
        'province': 'first', 'country': 'first',
        'year': 'first', 'month': 'first', 'day': 'first', 'season': 'first',
    }).reset_index()

    print(f"  Daily records: {len(daily):,}")

    # Date features
    daily['dayofyear'] = daily['date'].dt.dayofyear
    daily['dayofweek'] = daily['date'].dt.dayofweek
    daily['day_sin'] = np.sin(2 * np.pi * daily['dayofyear'] / 365)
    daily['day_cos'] = np.cos(2 * np.pi * daily['dayofyear'] / 365)
    daily['month_sin'] = np.sin(2 * np.pi * daily['month'] / 12)
    daily['month_cos'] = np.cos(2 * np.pi * daily['month'] / 12)
    daily['week_sin'] = np.sin(2 * np.pi * (daily['dayofyear'] // 7) / 52)
    daily['week_cos'] = np.cos(2 * np.pi * (daily['dayofyear'] // 7) / 52)
    daily['monsoon_cycle_day'] = (daily['dayofyear'] - 152) % 365

    # Seasonal flags
    daily['is_wet_season'] = daily['month'].isin([6,7,8,9,10,11]).astype(int)
    daily['is_dry_season'] = daily['month'].isin([1,2,3,4,5,12]).astype(int)
    daily['is_habagat'] = daily['month'].isin([6,7,8,9]).astype(int)
    daily['is_amihan'] = daily['month'].isin([10,11,12,1,2,3]).astype(int)
    daily['is_typhoon_season'] = daily['month'].isin([6,7,8,9,10,11]).astype(int)
    daily['is_typhoon_peak'] = daily['month'].isin([8,9,10]).astype(int)
    daily['is_hot_dry'] = daily['month'].isin([3,4,5]).astype(int)
    daily['is_transition'] = daily['month'].isin([5,6,11,12]).astype(int)
    daily['is_monsoon_transition'] = daily['month'].isin([5,6,11,12]).astype(int)

    # Lunar
    daily['lunar_phase'] = (daily['dayofyear'] % 29.53) / 29.53
    daily['lunar_sin'] = np.sin(2 * np.pi * daily['lunar_phase'])
    daily['lunar_cos'] = np.cos(2 * np.pi * daily['lunar_phase'])

    # Geospatial
    daily['lat'] = daily['municipality'].map(lambda m: GEO.get(m, {}).get('lat', 13.0))
    daily['lon'] = daily['municipality'].map(lambda m: GEO.get(m, {}).get('lon', 121.0))
    daily['elev'] = daily['municipality'].map(lambda m: GEO.get(m, {}).get('elev', 10))
    daily['coast_km'] = daily['municipality'].map(lambda m: GEO.get(m, {}).get('coast_km', 5))
    daily['lat_norm'] = (daily['lat'] - 6) / 12
    daily['lon_norm'] = (daily['lon'] - 117) / 10
    daily['coast_km_log'] = np.log1p(daily['coast_km'])
    daily['elev_norm'] = daily['elev'] / 1000

    # ENSO
    daily['enso_index'] = daily['year'].map(lambda y: ENSO.get(y, 0.0))
    daily['is_el_nino'] = (daily['enso_index'] > 0.5).astype(int)
    daily['is_la_nina'] = (daily['enso_index'] < -0.5).astype(int)

    # Interaction features
    daily['temp_humidity'] = daily['temperature'] * daily['humidity']
    daily['temp_x_humidity'] = daily['temperature'] * daily['humidity']
    daily['pressure_wind'] = daily['pressure'] * daily['wind_speed']
    daily['pressure_x_wind'] = daily['pressure'] * daily['wind_speed']
    daily['temp_x_rain'] = daily['temperature'] * daily['rainfall']
    daily['humidity_x_rain'] = daily['humidity'] * daily['rainfall']
    daily['wind_x_rain'] = daily['wind_speed'] * daily['rainfall']
    daily['humidity_sq'] = daily['humidity'] ** 2
    daily['pressure_sq'] = daily['pressure'] ** 2
    daily['dew_point'] = daily['temperature'] - ((100 - daily['humidity']) / 5)
    daily['dew_point_approx'] = daily['dew_point']

    # Extreme indicators
    daily['is_hot'] = (daily['temperature'] > 33).astype(int)
    daily['is_cold'] = (daily['temperature'] < 22).astype(int)
    daily['is_heavy_rain'] = (daily['rainfall'] > 20).astype(int)
    daily['is_very_heavy_rain'] = (daily['rainfall'] > 50).astype(int)
    daily['is_high_wind'] = (daily['wind_speed'] > 30).astype(int)
    daily['is_storm_wind'] = (daily['wind_speed'] > 60).astype(int)
    daily['is_low_pressure'] = (daily['pressure'] < 1005).astype(int)
    daily['is_very_low_pressure'] = (daily['pressure'] < 995).astype(int)
    daily['is_typhoon_conditions'] = ((daily['wind_speed'] > 60) & (daily['pressure'] < 1000) & (daily['rainfall'] > 50)).astype(int)
    daily['rain_yesterday'] = 0  # will be filled by lag features

    # Lag / rolling features per municipality
    print("  Computing lag and rolling features per municipality...")
    lag_cols = []
    for param in TARGETS:
        for lag in [1, 2, 3, 5, 7]:
            col = f'{param}_lag{lag}'
            lag_cols.append(col)
            daily[col] = daily.groupby('municipality')[param].shift(lag)
        daily[f'{param}_lag3_avg'] = daily.groupby('municipality')[param].transform(lambda x: x.shift(1).rolling(3).mean())
        daily[f'{param}_lag7_avg'] = daily.groupby('municipality')[param].transform(lambda x: x.shift(1).rolling(7).mean())
        for window in [3, 7, 14]:
            daily[f'{param}_roll_mean_{window}'] = daily.groupby('municipality')[param].transform(lambda x: x.shift(1).rolling(window).mean())
            daily[f'{param}_roll_std_{window}'] = daily.groupby('municipality')[param].transform(lambda x: x.shift(1).rolling(window).std())
            daily[f'{param}_roll_max_{window}'] = daily.groupby('municipality')[param].transform(lambda x: x.shift(1).rolling(window).max())
            daily[f'{param}_roll_min_{window}'] = daily.groupby('municipality')[param].transform(lambda x: x.shift(1).rolling(window).min())
        daily[f'{param}_std7'] = daily[f'{param}_roll_std_7']
        daily[f'{param}_diff1'] = daily.groupby('municipality')[param].diff(1)
        daily[f'{param}_diff3'] = daily.groupby('municipality')[param].diff(3)
        daily[f'{param}_ewm7'] = daily.groupby('municipality')[param].transform(lambda x: x.shift(1).ewm(span=7).mean())
        daily[f'{param}_ewm14'] = daily.groupby('municipality')[param].transform(lambda x: x.shift(1).ewm(span=14).mean())
        roll7 = daily[f'{param}_roll_mean_7']
        roll14 = daily[f'{param}_roll_mean_14']
        daily[f'{param}_anomaly_7d'] = daily[param] - roll7
        daily[f'{param}_anomaly_14d'] = daily[param] - roll14
        daily[f'{param}_anomaly'] = daily[f'{param}_anomaly_7d']

    daily['rain_yesterday'] = (daily['rainfall_lag1'] > 0).astype(int)
    daily['rain_3day_sum'] = daily['rainfall_lag1'].fillna(0) + daily['rainfall_lag2'].fillna(0) + daily['rainfall_lag3'].fillna(0)
    daily['rain_7day_sum'] = sum(daily.get(f'rainfall_lag{i}', pd.Series(0, index=daily.index)).fillna(0) for i in range(1, 8))
    daily['pressure_drop_1d'] = daily['pressure_diff1']
    daily['pressure_drop_3d'] = daily['pressure_diff3']
    daily['humidity_rise_1d'] = daily['humidity_diff1']
    daily['rainfall_roll3_max'] = daily['rainfall_roll_max_3']
    daily['rainfall_roll7_max'] = daily['rainfall_roll_max_7']

    # Historical comparison
    hist_means = daily.groupby('municipality')[TARGETS].transform('mean')
    for param in TARGETS:
        daily[f'hist_{param}_mean'] = hist_means[param]
        daily[f'{param}_vs_hist'] = daily[param] - hist_means[param]

    # Drop rows with NaN (from lag computation)
    before = len(daily)
    daily.dropna(inplace=True)
    print(f"  Dropped {before - len(daily)} rows with NaN (lag warmup). Remaining: {len(daily):,}")

    # Normalize targets to [0,1]
    for t in TARGETS:
        daily[f'{t}_norm'] = normalize(t, daily[t])

    elapsed = time.time() - t0
    print(f"  Feature engineering done in {elapsed:.1f}s. Columns: {len(daily.columns)}")
    return daily


def get_feature_cols(daily_df, target):
    """Return the feature columns for training (everything except targets, metadata, norms)."""
    exclude = set(TARGETS) | {f'{t}_norm' for t in TARGETS}
    exclude |= {'date', 'municipality', 'province', 'country', 'weather_condition', 'season'}
    cols = [c for c in daily_df.columns if c not in exclude]
    return cols


def train_xgboost_models(daily):
    """Train XGBoost v3 models + quantile models for each target."""
    import xgboost as xgb

    metrics_all = {}

    for target in TARGETS:
        print(f"\n{'='*60}")
        print(f"  Training XGBoost v3 for: {target}")
        print(f"{'='*60}")

        feat_cols = get_feature_cols(daily, target)
        target_col = f'{target}_norm'

        X = daily[feat_cols].values.astype(np.float32)
        y = daily[target_col].values.astype(np.float32)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)
        print(f"  Train: {len(X_train):,}  Test: {len(X_test):,}  Features: {len(feat_cols)}")

        # Main regression model with high-accuracy hyperparameters
        model = xgb.XGBRegressor(
            n_estimators=800,
            max_depth=8,
            learning_rate=0.03,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            reg_alpha=0.1,
            reg_lambda=1.0,
            tree_method='hist',
            random_state=42,
            n_jobs=-1,
            early_stopping_rounds=30,
        )

        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=50,
        )

        y_pred = model.predict(X_test)

        # Denormalize for real-unit metrics
        y_test_real = denormalize(target, y_test)
        y_pred_real = denormalize(target, y_pred)

        rmse_norm = float(np.sqrt(mean_squared_error(y_test, y_pred)))
        mae_real = float(mean_absolute_error(y_test_real, y_pred_real))
        rmse_real = float(np.sqrt(mean_squared_error(y_test_real, y_pred_real)))
        r2 = float(r2_score(y_test, y_pred))

        print(f"  Results (normalized): RMSE={rmse_norm:.4f}  R2={r2:.4f}")
        print(f"  Results (real units): MAE={mae_real:.3f}  RMSE={rmse_real:.3f}")

        metrics_all[target] = {'rmse': rmse_norm, 'mae_real': mae_real, 'rmse_real': rmse_real, 'r2': r2}

        # Save model + features
        joblib.dump(model, MODELS_DIR / f'xgboost_{target}_v3.pkl')
        joblib.dump(feat_cols, MODELS_DIR / f'xgboost_{target}_v3_features.pkl')
        # Also save as the primary model for backward compat
        joblib.dump(model, MODELS_DIR / f'{target}_model.pkl')
        joblib.dump(feat_cols, MODELS_DIR / f'{target}_feature_cols.pkl')
        print(f"  Saved xgboost_{target}_v3.pkl + feature list")

        # Quantile models (lower = 0.05, upper = 0.95 for 90% CI)
        for q_label, q_val, q_file in [('lower', 0.05, 'qlower_v3'), ('upper', 0.95, 'qupper_v3')]:
            q_model = xgb.XGBRegressor(
                n_estimators=400,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                objective='reg:quantileerror',
                quantile_alpha=q_val,
                tree_method='hist',
                random_state=42,
                n_jobs=-1,
            )
            q_model.fit(X_train, y_train, verbose=0)
            joblib.dump(q_model, MODELS_DIR / f'xgboost_{target}_{q_file}.pkl')
            print(f"  Saved xgboost_{target}_{q_file}.pkl")

    return metrics_all


def train_condition_model(daily):
    """Train weather condition classifier + encoder."""
    print("\n" + "="*60)
    print("  Training Condition Classifier")
    print("="*60)

    le = LabelEncoder()
    daily['condition_encoded'] = le.fit_transform(daily['weather_condition'])
    print(f"  Classes: {list(le.classes_)}")

    feat_cols = get_feature_cols(daily, 'temperature')  # reuse same features
    X = daily[feat_cols].values.astype(np.float32)
    y = daily['condition_encoded'].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)

    from sklearn.ensemble import GradientBoostingClassifier
    clf = GradientBoostingClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05, random_state=42,
    )
    clf.fit(X_train, y_train)
    acc = clf.score(X_test, y_test)
    print(f"  Condition accuracy: {acc:.4f}")

    joblib.dump(clf, MODELS_DIR / 'condition_model.pkl')
    joblib.dump(le, MODELS_DIR / 'condition_encoder.pkl')
    print("  Saved condition_model.pkl + condition_encoder.pkl")

    return acc


def train_correction_models(daily):
    """Train OpenWeather → local correction models (RandomForest)."""
    print("\n" + "="*60)
    print("  Training Correction Models")
    print("="*60)

    # Simulate "OpenWeather" as the raw values + small noise, train to predict actual local
    for param in TARGETS:
        noise = np.random.normal(0, daily[param].std() * 0.1, len(daily))
        daily[f'ow_{param}'] = daily[param] + noise

    for param in ['temperature', 'humidity', 'pressure', 'wind_speed']:
        ow_features = ['ow_temperature', 'ow_humidity', 'ow_pressure', 'ow_wind_speed']
        X = daily[ow_features].values
        y = daily[param].values

        model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
        model.fit(X, y)

        y_pred = model.predict(X)
        mae = mean_absolute_error(y, y_pred)
        print(f"  {param} correction MAE: {mae:.3f}")

        # Save with feature names expected by predictor
        # predictor sends: [temperature, humidity, pressure, wind_speed, visibility, clouds]
        # We pad visibility=10 and clouds=50 during training
        X_full = np.column_stack([X, np.full(len(X), 10.0), np.full(len(X), 50.0)])
        model_full = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
        model_full.fit(X_full, y)

        fname = f'correction_{param}_model.pkl'
        if param == 'temperature':
            fname = 'correction_temp_model.pkl'
        joblib.dump(model_full, MODELS_DIR / fname)
        print(f"  Saved {fname}")


def save_last_data(daily):
    """Save last_data.pkl used by ML-only fallback."""
    last = daily.iloc[-1]
    last_data = {
        'temperature': float(last['temperature']),
        'humidity': float(last['humidity']),
        'rainfall': float(last['rainfall']),
        'wind_speed': float(last['wind_speed']),
        'pressure': float(last['pressure']),
        'condition': last['weather_condition'],
    }
    joblib.dump(last_data, MODELS_DIR / 'last_data.pkl')
    print(f"\n  Saved last_data.pkl: {last_data}")


def save_featured_csv(daily):
    """Save the featured dataset for use by the predictor at runtime."""
    out_path = DATA_DIR / 'philippines_weather_featured_v3.csv'
    daily.to_csv(out_path, index=False)
    print(f"  Saved featured CSV: {out_path} ({len(daily):,} rows, {out_path.stat().st_size / 1024 / 1024:.1f} MB)")


def main():
    print("=" * 70)
    print("  Shrimply Smart — Production Weather Model Training")
    print(f"  Dataset: {MERGED_CSV}")
    print("=" * 70)

    # Load data
    print(f"\n[LOAD] Reading merged dataset...")
    df = pd.read_csv(MERGED_CSV)
    print(f"  Total rows: {len(df):,}")
    print(f"  Calapan rows: {len(df[df['municipality'] == 'Calapan']):,}")
    print(f"  Municipalities: {df['municipality'].nunique()}")

    # Feature engineering
    daily = build_features(df)

    # Save featured CSV for runtime
    save_featured_csv(daily)

    # Train XGBoost v3 models
    metrics = train_xgboost_models(daily)

    # Save model metrics
    metrics_path = MODELS_DIR / 'weather_model_metrics.json'
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  Saved model metrics to {metrics_path}")

    # Train condition classifier
    cond_acc = train_condition_model(daily)
    metrics['condition'] = {'accuracy': cond_acc}

    # Train correction models
    train_correction_models(daily)

    # Save last_data fallback
    save_last_data(daily)

    # Final summary
    print("\n" + "=" * 70)
    print("  TRAINING COMPLETE — Summary")
    print("=" * 70)
    for target, m in metrics.items():
        if 'r2' in m:
            print(f"  {target:15s}  R2={m['r2']:.4f}  MAE={m.get('mae_real', 'N/A')}  RMSE={m.get('rmse_real', 'N/A')}")
        elif 'accuracy' in m:
            print(f"  {target:15s}  Accuracy={m['accuracy']:.4f}")
    print("=" * 70)
    print("  All models saved to:", MODELS_DIR)
    print("  Restart Django to load new models automatically.")
    print("=" * 70)


if __name__ == '__main__':
    main()
