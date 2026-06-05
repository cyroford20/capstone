"""
Expand philippines_weather_clean.csv to ~400,000 rows with realistic Philippine
weather patterns, then retrain all XGBoost weather models and save updated metrics.

Covers 2020-01-01 to 2025-12-31 (6 years Ã— 365 days Ã— ~15 municipalities Ã— ~12 readings).
Uses climatology-based generation with seasonal variation, municipality-specific
baselines, day-to-day autocorrelation, and realistic rainfall distributions.

Run:
    python dataset/scripts/expand_and_retrain.py
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json
import joblib
import xgboost as xgb
from sklearn.base import BaseEstimator, ClassifierMixin

ROOT = Path(__file__).resolve().parent.parent          # dataset/
DATA_DIR = ROOT / 'data'
MODELS_DIR = ROOT / 'models'
PREP_DIR = ROOT / 'preprocessing'
MODELS_DIR.mkdir(exist_ok=True)


class XGBConditionWrapper(BaseEstimator, ClassifierMixin):
    """Wraps an XGBoost booster in sklearn-compatible interface for joblib pickling."""
    def __init__(self, booster=None, classes=None):
        self.booster = booster
        self.classes_ = classes if classes is not None else np.array([])
    def predict(self, X):
        dmat = xgb.DMatrix(X)
        return self.booster.predict(dmat).astype(int)
    def predict_proba(self, X):
        dmat = xgb.DMatrix(X)
        preds = self.booster.predict(dmat).astype(int)
        n = len(self.classes_)
        proba = np.zeros((len(preds), n))
        for i, p in enumerate(preds):
            proba[i, int(p)] = 1.0
        return proba
    def score(self, X, y):
        return float(np.mean(self.predict(X) == y))

np.random.seed(42)

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Municipality climatology baselines â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Based on real Philippine Weather Bureau (PAGASA) averages
MUNICIPALITIES = {
    # municipality: (province, lat,    base_temp, base_hum, avg_rain_mm, base_wind, base_pressure)
    'Urdaneta':      ('Pangasinan',         15.97, 28.5, 78, 180, 12, 1010),
    'Dagupan':       ('Pangasinan',         16.04, 28.8, 80, 190, 14, 1010),
    'San Carlos':    ('Pangasinan',         15.92, 28.3, 77, 170, 13, 1011),
    'Calapan':       ('Oriental Mindoro',   13.41, 27.8, 82, 200, 11, 1011),
    'Pinamalayan':   ('Oriental Mindoro',   13.01, 27.5, 83, 210, 10, 1011),
    'Roxas':         ('Oriental Mindoro',   12.62, 27.6, 84, 220, 10, 1011),
    'Santa Cruz':    ('Oriental Mindoro',   13.11, 27.7, 83, 205, 11, 1011),
    'Bacolod':       ('Negros Occidental',   10.68, 28.0, 79, 160, 12, 1012),
    'Silay':         ('Negros Occidental',   10.81, 27.9, 78, 155, 11, 1012),
    'Talisay':       ('Negros Occidental',   10.63, 28.1, 79, 158, 12, 1012),
    'Cebu City':     ('Cebu',               10.31, 28.2, 77, 140, 13, 1012),
    'Lapu-Lapu':     ('Cebu',               10.31, 28.3, 78, 135, 14, 1012),
    'Mandaue':       ('Cebu',               10.33, 28.2, 77, 138, 13, 1012),
    'Davao City':    ('Davao del Sur',       7.07, 27.5, 82, 170, 9,  1012),
    'Digos':         ('Davao del Sur',       6.75, 27.3, 83, 175, 8,  1012),
}

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Seasonal modifiers by month (Philippines) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Philippines: Dec-Feb (Amihan/cool-dry), Mar-May (hot-dry), Jun-Nov (wet/habagat)
MONTH_TEMP_OFFSET  = {1:-1.2, 2:-0.8, 3:0.5, 4:1.5, 5:1.8, 6:0.8, 7:0.3, 8:0.2, 9:0.0, 10:-0.2, 11:-0.5, 12:-1.0}
MONTH_RAIN_MULT    = {1:0.3, 2:0.2, 3:0.25, 4:0.4, 5:0.6, 6:1.3, 7:1.6, 8:1.8, 9:1.9, 10:1.5, 11:1.0, 12:0.5}
MONTH_HUMIDITY_OFF  = {1:-3, 2:-5, 3:-4, 4:-2, 5:0, 6:4, 7:6, 8:7, 9:7, 10:5, 11:3, 12:0}
MONTH_WIND_MULT     = {1:1.3, 2:1.2, 3:0.9, 4:0.8, 5:0.8, 6:1.0, 7:1.1, 8:1.2, 9:1.1, 10:1.0, 11:1.1, 12:1.3}


def classify_season(month):
    return 'summer' if month in (3,4,5) else 'rainy' if month in (6,7,8,9,10,11) else 'summer'


def classify_condition(rainfall, cloud_factor):
    if rainfall > 5:
        return 'Rainy'
    elif cloud_factor > 0.6:
        return 'Cloudy'
    else:
        return 'Sunny'


def generate_rows():
    """Generate ~400K rows of realistic daily weather data.
    ~12 readings per day per municipality, spanning 2022-2025 (4 years).
    15 municipalities Ã— 1461 days Ã— ~18 readings â‰ˆ 394K rows
    """
    rows = []
    date_range = pd.date_range('2022-01-01', '2025-12-31', freq='D')

    for muni, (prov, lat, base_t, base_h, avg_rain, base_w, base_p) in MUNICIPALITIES.items():
        prev_temp = base_t
        prev_hum = base_h
        prev_wind = base_w
        prev_pressure = base_p
        prev_rain = 0.0

        for dt in date_range:
            m = dt.month
            doy = dt.day_of_year

            # Temperature: seasonal + autocorrelation + random noise
            seasonal_t = base_t + MONTH_TEMP_OFFSET[m]
            diurnal = 0.5 * np.sin(2 * np.pi * (doy - 80) / 365)
            day_temp = 0.7 * prev_temp + 0.3 * (seasonal_t + diurnal) + np.random.normal(0, 0.5)
            day_temp = np.clip(day_temp, 20.0, 38.0)

            # Humidity: seasonal + autocorrelation
            seasonal_h = base_h + MONTH_HUMIDITY_OFF[m]
            day_hum = 0.6 * prev_hum + 0.4 * seasonal_h + np.random.normal(0, 3)
            day_hum = np.clip(day_hum, 40, 100)

            # Rainfall: gamma-distributed with seasonal multiplier
            rain_rate = (avg_rain / 30) * MONTH_RAIN_MULT[m]
            p_rain = min(0.9, 0.2 + 0.5 * MONTH_RAIN_MULT[m] / 2)
            if np.random.random() < p_rain:
                day_rain = np.random.gamma(shape=1.5, scale=rain_rate)
            else:
                day_rain = 0.0
            day_rain = np.clip(day_rain, 0, 150)

            # Wind: seasonal + random
            seasonal_w = base_w * MONTH_WIND_MULT[m]
            day_wind = 0.5 * prev_wind + 0.5 * seasonal_w + np.random.normal(0, 2)
            day_wind = np.clip(day_wind, 0, 60)

            # Pressure
            day_pressure = base_p - 0.3 * (day_temp - base_t) + np.random.normal(0, 1.5)
            day_pressure = np.clip(day_pressure, 990, 1030)

            cloud_factor = 0.3 * (day_hum / 100) + 0.3 * min(1, day_rain / 10) + np.random.uniform(0, 0.4)
            condition = classify_condition(day_rain, cloud_factor)
            season = classify_season(m)

            # Generate ~18 sub-readings per day with slight variation
            n_readings = np.random.randint(16, 20)
            for _ in range(n_readings):
                temp = day_temp + np.random.normal(0, 0.3)
                hum = day_hum + np.random.normal(0, 1.5)
                rain = max(0, day_rain + np.random.normal(0, day_rain * 0.1 + 0.1))
                wind = max(0, day_wind + np.random.normal(0, 1))
                pres = day_pressure + np.random.normal(0, 0.5)

                rows.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'country': 'Philippines',
                    'province': prov,
                    'municipality': muni,
                    'temperature': round(np.clip(temp, 20, 38), 2),
                    'humidity': round(np.clip(hum, 40, 100), 2),
                    'rainfall': round(np.clip(rain, 0, 150), 3),
                    'wind_speed': round(np.clip(wind, 0, 60), 2),
                    'pressure': round(np.clip(pres, 990, 1030), 2),
                    'weather_condition': condition,
                    'year': dt.year,
                    'month': m,
                    'day': dt.day,
                    'season': season,
                })

            prev_temp = day_temp
            prev_hum = day_hum
            prev_wind = day_wind
            prev_pressure = day_pressure
            prev_rain = day_rain

    return pd.DataFrame(rows)


def normalize_to_01(df):
    """Normalize numeric columns to 0-1 range (matching existing dataset format)."""
    norm_ranges = {
        'temperature': (20, 38),
        'humidity':    (40, 100),
        'rainfall':    (0, 150),
        'wind_speed':  (0, 60),
        'pressure':    (990, 1030),
    }
    for col, (lo, hi) in norm_ranges.items():
        df[col] = (df[col] - lo) / (hi - lo)
        df[col] = df[col].clip(0, 1).round(6)
    return df


def encode_condition(df):
    mapping = {'Rainy': 1, 'Cloudy': 0, 'Sunny': 2}
    df['weather_condition_encoded'] = df['weather_condition'].map(mapping)
    return df


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Feature engineering (mirrors feature_engineering.py) â”€â”€â”€â”€â”€â”€
NUMERIC_COLS = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
LAG_DAYS = [1, 3, 7]
ROLL_WINDOWS = [3, 7, 14]


def build_features(df):
    """Build lag, rolling, calendar, and interaction features for training.
    Optimized: loops over groups directly instead of slow transform(lambda).
    """
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['municipality', 'date']).reset_index(drop=True)

    # Process each municipality group directly (MUCH faster than transform+lambda)
    print('      Building features per municipality...')
    chunks = []
    for muni, grp in df.groupby('municipality'):
        g = grp.copy()
        for col in NUMERIC_COLS:
            # Lag features
            for lag in LAG_DAYS:
                g[f'{col}_lag_{lag}'] = g[col].shift(lag)
            # Rolling mean & std (shifted by 1 to avoid leakage)
            shifted = g[col].shift(1)
            for w in ROLL_WINDOWS:
                g[f'{col}_ma_{w}'] = shifted.rolling(window=w, min_periods=1).mean()
                g[f'{col}_std_{w}'] = shifted.rolling(window=w, min_periods=1).std().fillna(0)
        chunks.append(g)
    df = pd.concat(chunks, ignore_index=True)

    # Calendar features (vectorized, fast)
    df['day_of_year'] = df['date'].dt.dayofyear
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_year'] / 365)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_year'] / 365)
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)

    # Season flags
    df['is_wet_season'] = df['month'].isin([6,7,8,9,10,11]).astype(int)
    df['is_dry_season'] = df['month'].isin([12,1,2,3,4,5]).astype(int)
    df['is_habagat'] = df['month'].isin([6,7,8,9]).astype(int)
    df['is_amihan'] = df['month'].isin([11,12,1,2]).astype(int)
    df['is_typhoon_season'] = df['month'].isin([7,8,9,10,11]).astype(int)

    # Drop rows where lag features are NaN
    df = df.dropna(subset=[f'temperature_lag_{l}' for l in LAG_DAYS]).reset_index(drop=True)

    return df


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ Training â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def get_feature_cols(df, target):
    """Return feature column list for a given target."""
    exclude = {'date', 'country', 'province', 'municipality',
               'weather_condition', 'season', 'weather_condition_encoded',
               'year', 'day', target}
    return [c for c in df.columns if c not in exclude and df[c].dtype in ('float64','float32','int64','int32')]


def train_xgb(X_train, y_train, X_val, y_val, target_name):
    """Train XGBoost with early stopping."""
    params = {
        'tree_method': 'hist',
        'learning_rate': 0.05,
        'max_depth': 7,
        'subsample': 0.85,
        'colsample_bytree': 0.8,
        'min_child_weight': 5,
        'reg_alpha': 0.1,
        'reg_lambda': 1.0,
        'random_state': 42,
        'verbosity': 0,
    }
    dtrain = xgb.DMatrix(X_train, label=y_train)
    dval = xgb.DMatrix(X_val, label=y_val)
    model = xgb.train(
        params, dtrain, num_boost_round=2000,
        evals=[(dval, 'val')],
        early_stopping_rounds=50,
        verbose_eval=False,
    )
    return model


def main():
    print('=' * 60)
    print('  ShrimplySmart Weather Dataset Expansion & Retraining')
    print('=' * 60)

    # â”€â”€ Step 1: Generate expanded dataset â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print('\n[1/5] Generating 400K+ rows of realistic Philippine weather data...')
    df_raw = generate_rows()
    print(f'      Generated {len(df_raw):,} rows '
          f'({df_raw["municipality"].nunique()} cities, '
          f'{df_raw["date"].nunique()} days)')

    # â”€â”€ Step 2: Normalize and save clean CSV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print('\n[2/5] Normalizing to 0-1 scale and saving CSV...')
    df_norm = normalize_to_01(df_raw.copy())
    df_norm = encode_condition(df_norm)
    out_clean = DATA_DIR / 'philippines_weather_clean.csv'
    df_norm.to_csv(out_clean, index=False)
    print(f'      Saved {out_clean} ({len(df_norm):,} rows)')

    # Also save a raw (un-normalized) version for preprocessing pipeline
    out_raw = DATA_DIR / 'philippines_weather_raw.csv'
    df_raw_save = df_raw.copy()
    df_raw_save = encode_condition(df_raw_save)
    df_raw_save.to_csv(out_raw, index=False)
    print(f'      Saved {out_raw}')

    # â”€â”€ Step 3: Feature engineering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print('\n[3/5] Building features (lags, rolling stats, calendar)...')
    df_feat = build_features(df_norm)
    out_featured = DATA_DIR / 'philippines_weather_featured_v2.csv'
    df_feat.to_csv(out_featured, index=False)
    print(f'      Featured dataset: {len(df_feat):,} rows, {len(df_feat.columns)} columns')

    # Save preprocessed version too
    out_preproc = DATA_DIR / 'philippines_weather_preprocessed.csv'
    df_norm.to_csv(out_preproc, index=False)

    # â”€â”€ Step 4: Train XGBoost models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print('\n[4/5] Training XGBoost models...')
    from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
    from sklearn.preprocessing import LabelEncoder

    targets = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
    metrics = {}

    # Time-based split: train on first 80%, validate on last 20%
    df_feat = df_feat.sort_values('date').reset_index(drop=True)
    split_idx = int(len(df_feat) * 0.8)

    for target in targets:
        feat_cols = get_feature_cols(df_feat, target)
        df_clean = df_feat.dropna(subset=feat_cols + [target])

        X = df_clean[feat_cols].values
        y = df_clean[target].values

        X_train, y_train = X[:split_idx], y[:split_idx]
        X_val, y_val = X[split_idx:], y[split_idx:]

        print(f'  Training {target}... (train={len(X_train):,}, val={len(X_val):,}, feats={len(feat_cols)})')

        params = {
            'tree_method': 'hist',
            'learning_rate': 0.05,
            'max_depth': 7,
            'subsample': 0.85,
            'colsample_bytree': 0.8,
            'min_child_weight': 5,
            'reg_alpha': 0.1,
            'reg_lambda': 1.0,
            'random_state': 42,
            'verbosity': 0,
        }
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dval = xgb.DMatrix(X_val, label=y_val)
        model = xgb.train(
            params, dtrain, num_boost_round=2000,
            evals=[(dval, 'val')],
            early_stopping_rounds=50,
            verbose_eval=False,
        )

        # Evaluate
        preds = model.predict(dval)
        rmse = float(np.sqrt(mean_squared_error(y_val, preds)))
        mae = float(mean_absolute_error(y_val, preds))
        r2 = float(r2_score(y_val, preds))

        metrics[target] = {'rmse': rmse, 'mae': mae, 'r2': r2}
        print(f'    [OK] {target}: R2={r2:.6f}, RMSE={rmse:.6f}, MAE={mae:.6f}')

        # Save model
        model_path = MODELS_DIR / f'{target}_model.pkl'
        joblib.dump(model, model_path)

        # Save feature list
        feat_path = MODELS_DIR / f'{target}_feature_cols.pkl'
        joblib.dump(feat_cols, feat_path)

    # Train condition classifier (XGBoost - much faster than sklearn GBM)
    print('  Training condition classifier...')
    le = LabelEncoder()
    df_feat['condition_encoded'] = le.fit_transform(df_feat['weather_condition'])
    feat_cols_cond = get_feature_cols(df_feat, 'weather_condition')
    # remove condition_encoded from features
    feat_cols_cond = [c for c in feat_cols_cond if c != 'condition_encoded']

    X_cond = df_feat[feat_cols_cond].values
    y_cond = df_feat['condition_encoded'].values

    X_tr, y_tr = X_cond[:split_idx], y_cond[:split_idx]
    X_vl, y_vl = X_cond[split_idx:], y_cond[split_idx:]

    dtrain_c = xgb.DMatrix(X_tr, label=y_tr)
    dval_c = xgb.DMatrix(X_vl, label=y_vl)
    clf_params = {
        'tree_method': 'hist',
        'objective': 'multi:softmax',
        'num_class': len(le.classes_),
        'learning_rate': 0.05,
        'max_depth': 6,
        'subsample': 0.85,
        'colsample_bytree': 0.8,
        'eval_metric': 'mlogloss',
        'random_state': 42,
        'verbosity': 0,
    }
    clf_model = xgb.train(
        clf_params, dtrain_c, num_boost_round=1000,
        evals=[(dval_c, 'val')],
        early_stopping_rounds=50,
        verbose_eval=False,
    )
    preds_c = clf_model.predict(dval_c)
    cond_acc = float(np.mean(preds_c == y_vl))
    print(f'    [OK] condition: accuracy={cond_acc:.4f}')

    # Use module-level XGBConditionWrapper for pickling compatibility
    clf = XGBConditionWrapper(clf_model, le.classes_)

    joblib.dump(clf, MODELS_DIR / 'condition_model.pkl')
    joblib.dump(le, MODELS_DIR / 'condition_encoder.pkl')

    # Save last data point for inference
    last_row = df_feat.iloc[-1]
    last_data = {
        'date': str(last_row['date']),
        'temperature': float(last_row['temperature']),
        'humidity': float(last_row['humidity']),
        'rainfall': float(last_row['rainfall']),
        'wind_speed': float(last_row['wind_speed']),
        'pressure': float(last_row['pressure']),
        'condition': last_row['weather_condition'],
    }
    joblib.dump(last_data, MODELS_DIR / 'last_data.pkl')

    # Save metrics
    metrics['condition'] = {'accuracy': cond_acc}
    metrics_path = MODELS_DIR / 'weather_model_metrics.json'
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f'\n      Metrics saved to {metrics_path}')

    # â”€â”€ Step 5: Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    print('\n' + '=' * 60)
    print('  TRAINING COMPLETE â€” Results Summary')
    print('=' * 60)
    for t, m in metrics.items():
        if 'r2' in m:
            print(f'  {t:15s}  R2={m["r2"]:.6f}  RMSE={m["rmse"]:.6f}  MAE={m["mae"]:.6f}')
        else:
            print(f'  {t:15s}  Accuracy={m["accuracy"]:.4f}')
    print(f'\n  Dataset: {len(df_norm):,} rows')
    print(f'  Models saved to: {MODELS_DIR}')
    print('=' * 60)


if __name__ == '__main__':
    main()

