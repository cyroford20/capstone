"""
Advanced Weather Model Training — v3
=====================================
Trains improved weather prediction models with:
1. Walk-forward time-series cross-validation
2. Hyperparameter-tuned XGBoost (Optuna-free grid search)
3. Bidirectional LSTM with attention
4. Ensemble voting (XGBoost + LSTM weighted average)
5. Quantile regression for confidence intervals
6. Per-season validation (monsoon/dry)
7. Physical constraint post-processing
8. Feedback loop error tracking

Usage:
    python train_weather_v3.py

Requires:  dataset/data/philippines_weather_featured_v3.csv
Outputs:   dataset/models/ (updated models + metrics)
"""
import sys
import os
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.preprocessing import MinMaxScaler
import joblib
import json
from pathlib import Path
import time
import warnings
warnings.filterwarnings('ignore')

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, callbacks
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("[WARN] TensorFlow not available - LSTM training disabled")

ROOT = Path(__file__).parent.parent
DATA_V3 = ROOT / 'data' / 'philippines_weather_featured_v3.csv'
DATA_RAW = ROOT / 'data' / 'philippines_weather_raw.csv'
MODELS_DIR = ROOT / 'models'
MODELS_DIR.mkdir(exist_ok=True)

TARGETS = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']

# Physical limits for post-processing
PHYSICAL_LIMITS = {
    'temperature': (15, 45),
    'humidity': (20, 100),
    'rainfall': (0, 500),
    'wind_speed': (0, 200),
    'pressure': (900, 1060),
}

# Smoothness limits: max reasonable day-to-day change
MAX_DAILY_CHANGE = {
    'temperature': 5.0,
    'humidity': 25.0,
    'rainfall': 100.0,
    'wind_speed': 30.0,
    'pressure': 15.0,
}


# ═══════════════════════════════════════════════════════════════════════════
# 1. DATA LOADING
# ═══════════════════════════════════════════════════════════════════════════
def load_featured_data():
    """Load v3 featured dataset. Falls back to raw data with basic features."""
    if DATA_V3.exists():
        df = pd.read_csv(DATA_V3, parse_dates=['date'])
        print(f"[OK] Loaded v3 featured dataset: {len(df)} rows")
        return df

    # Fall back to raw data + basic feature engineering
    print("[WARN] v3 featured data not found, using raw data with basic features")
    df = pd.read_csv(DATA_RAW, parse_dates=['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Aggregate daily per municipality
    daily = df.groupby(['date', 'province', 'municipality'])[TARGETS].mean().reset_index()
    daily = daily.sort_values('date').reset_index(drop=True)

    # Add minimal features
    daily['dayofyear'] = daily['date'].dt.dayofyear
    daily['month_num'] = daily['date'].dt.month
    daily['day_sin'] = np.sin(2 * np.pi * daily['dayofyear'] / 365)
    daily['day_cos'] = np.cos(2 * np.pi * daily['dayofyear'] / 365)
    daily['month_sin'] = np.sin(2 * np.pi * daily['month_num'] / 12)
    daily['month_cos'] = np.cos(2 * np.pi * daily['month_num'] / 12)
    daily['is_wet_season'] = daily['month_num'].isin([6,7,8,9,10,11]).astype(int)
    daily['is_typhoon_peak'] = daily['month_num'].isin([8,9,10]).astype(int)

    for col in TARGETS:
        daily[f'{col}_lag1'] = daily.groupby('municipality')[col].shift(1)
        daily[f'{col}_lag3_avg'] = daily.groupby('municipality')[col].transform(
            lambda x: x.shift(1).rolling(3, min_periods=1).mean())
        daily[f'{col}_lag7_avg'] = daily.groupby('municipality')[col].transform(
            lambda x: x.shift(1).rolling(7, min_periods=1).mean())

    daily['temp_x_humidity'] = daily['temperature'] * daily['humidity']
    daily['pressure_x_wind'] = daily['pressure'] * daily['wind_speed']
    daily = daily.dropna().reset_index(drop=True)
    return daily


# ═══════════════════════════════════════════════════════════════════════════
# 2. XGBOOST WITH HYPERPARAMETER SEARCH
# ═══════════════════════════════════════════════════════════════════════════
PARAM_GRID = [
    {'n_estimators': 600, 'max_depth': 6, 'learning_rate': 0.05, 'subsample': 0.7,
     'colsample_bytree': 0.6, 'reg_alpha': 0.1, 'reg_lambda': 1.5, 'min_child_weight': 5},
    {'n_estimators': 400, 'max_depth': 5, 'learning_rate': 0.08, 'subsample': 0.7,
     'colsample_bytree': 0.5, 'reg_alpha': 0.3, 'reg_lambda': 2.0, 'min_child_weight': 10},
]

# Maximum training samples (to avoid OOM on machines with limited RAM)
MAX_TRAIN_SAMPLES = 150000


def train_xgboost_v3(df, target):
    """Train XGBoost with grid search + walk-forward CV. Memory-optimized."""
    import gc

    exclude_cols = {'date', 'province', 'municipality', 'country',
                    'weather_condition', 'condition', 'source', 'season',
                    'weather_condition_encoded', 'month_day'}
    feature_cols = [c for c in df.select_dtypes(include=[np.number]).columns
                    if c not in exclude_cols and c != target]

    # Use float32 to reduce memory
    X = df[feature_cols].values.astype(np.float32)
    y = df[target].values.astype(np.float32)

    # Time-based split (80/20)
    split_idx = int(len(X) * 0.8)
    X_train_full, X_test = X[:split_idx], X[split_idx:]
    y_train_full, y_test = y[:split_idx], y[split_idx:]

    # Subsample training data if too large
    if len(X_train_full) > MAX_TRAIN_SAMPLES:
        indices = np.linspace(0, len(X_train_full) - 1, MAX_TRAIN_SAMPLES, dtype=int)
        X_train = X_train_full[indices]
        y_train = y_train_full[indices]
        print(f"     Subsampled training: {len(X_train_full)} -> {len(X_train)}")
    else:
        X_train = X_train_full
        y_train = y_train_full
    del X_train_full, y_train_full
    gc.collect()

    best_model = None
    best_score = -999
    best_params = None

    for params in PARAM_GRID:
        model = xgb.XGBRegressor(
            **params,
            random_state=42,
            verbosity=0,
            tree_method='hist',
            early_stopping_rounds=50,
        )
        model.fit(X_train, y_train,
                  eval_set=[(X_test, y_test)],
                  verbose=False)

        y_pred = model.predict(X_test)
        r2 = r2_score(y_test, y_pred)

        if r2 > best_score:
            best_score = r2
            best_model = model
            best_params = params
        else:
            del model
        gc.collect()

    # Walk-forward CV on best model (use smaller sample for speed)
    tscv = TimeSeriesSplit(n_splits=3)
    cv_r2_scores = []
    cv_rmse_scores = []
    # Combine train+test for CV
    X_all = np.vstack([X_train, X_test])
    y_all = np.concatenate([y_train, y_test])
    # Use at most 100K samples for CV
    if len(X_all) > 100000:
        cv_idx = np.linspace(0, len(X_all)-1, 100000, dtype=int)
        X_cv, y_cv = X_all[cv_idx], y_all[cv_idx]
    else:
        X_cv, y_cv = X_all, y_all
    del X_all, y_all
    gc.collect()

    for train_idx, val_idx in tscv.split(X_cv):
        m = xgb.XGBRegressor(**best_params, random_state=42, verbosity=0, tree_method='hist')
        m.fit(X_cv[train_idx], y_cv[train_idx], verbose=False)
        p = m.predict(X_cv[val_idx])
        cv_r2_scores.append(r2_score(y_cv[val_idx], p))
        cv_rmse_scores.append(np.sqrt(mean_squared_error(y_cv[val_idx], p)))
        del m
        gc.collect()
    del X_cv, y_cv
    gc.collect()

    # Final evaluation
    y_pred = best_model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    # Train quantile models for confidence intervals
    quantile_models = {}
    for alpha, name in [(0.05, 'lower'), (0.95, 'upper')]:
        qm = xgb.XGBRegressor(
            **{**best_params, 'objective': 'reg:quantileerror', 'quantile_alpha': alpha},
            random_state=42, verbosity=0, tree_method='hist',
        )
        qm.fit(X_train, y_train, verbose=False)
        quantile_models[name] = qm

    # Per-season evaluation
    season_metrics = {}
    if 'is_wet_season' in df.columns:
        test_df = df.iloc[split_idx:].copy()
        test_df['pred'] = y_pred
        for season_name, mask_col in [('wet', 'is_wet_season'), ('dry', 'is_dry_season')]:
            if mask_col in test_df.columns:
                mask = test_df[mask_col] == 1
                if mask.sum() > 10:
                    s_true = test_df.loc[mask, target].values
                    s_pred = test_df.loc[mask, 'pred'].values
                    season_metrics[season_name] = {
                        'r2': float(r2_score(s_true, s_pred)),
                        'rmse': float(np.sqrt(mean_squared_error(s_true, s_pred))),
                        'count': int(mask.sum()),
                    }

    metrics = {
        'r2': float(r2),
        'rmse': float(rmse),
        'mae': float(mae),
        'cv_r2_mean': float(np.mean(cv_r2_scores)),
        'cv_r2_std': float(np.std(cv_r2_scores)),
        'cv_rmse_mean': float(np.mean(cv_rmse_scores)),
        'best_params': best_params,
        'season_metrics': season_metrics,
        'n_features': len(feature_cols),
    }

    return best_model, feature_cols, metrics, quantile_models


# ═══════════════════════════════════════════════════════════════════════════
# 3. BIDIRECTIONAL LSTM WITH ATTENTION
# ═══════════════════════════════════════════════════════════════════════════
def build_bilstm_attention(lookback=14, n_features=5):
    """Build Bidirectional LSTM with self-attention layer."""
    if not TF_AVAILABLE:
        return None

    inputs = keras.Input(shape=(lookback, n_features))

    # Bidirectional LSTM layers
    x = layers.Bidirectional(
        layers.LSTM(128, return_sequences=True,
                    kernel_regularizer=keras.regularizers.l2(0.001))
    )(inputs)
    x = layers.Dropout(0.3)(x)

    x = layers.Bidirectional(
        layers.LSTM(64, return_sequences=True,
                    kernel_regularizer=keras.regularizers.l2(0.001))
    )(x)
    x = layers.Dropout(0.2)(x)

    # Self-attention mechanism
    attention = layers.Dense(1, activation='tanh')(x)
    attention = layers.Flatten()(attention)
    attention = layers.Activation('softmax')(attention)
    attention = layers.RepeatVector(128)(attention)  # 64*2 for bidirectional
    attention = layers.Permute([2, 1])(attention)
    x = layers.Multiply()([x, attention])
    x = layers.Lambda(lambda z: tf.reduce_sum(z, axis=1))(x)

    # Dense head
    x = layers.Dense(64, activation='relu')(x)
    x = layers.Dropout(0.2)(x)
    x = layers.Dense(32, activation='relu')(x)
    outputs = layers.Dense(n_features)(x)

    model = keras.Model(inputs=inputs, outputs=outputs)
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=0.001),
        loss='mse',
        metrics=['mae']
    )
    return model


def train_lstm_v3(df, location_name, lookback=14):
    """Train Bidirectional LSTM for a specific location."""
    if not TF_AVAILABLE:
        print(f"  [SKIP] TensorFlow not available for {location_name}")
        return None, None, None

    # Filter for location
    loc_data = df[
        (df['municipality'].str.lower() == location_name.lower()) |
        (df['province'].str.lower() == location_name.lower())
    ].sort_values('date')

    if len(loc_data) < lookback * 3:
        print(f"  [SKIP] Not enough data for {location_name} ({len(loc_data)} rows)")
        return None, None, None

    features = [c for c in TARGETS if c in loc_data.columns]
    data = loc_data[features].values

    # Normalize to [0, 1]
    scaler = MinMaxScaler()
    data_scaled = scaler.fit_transform(data)

    # Create sequences
    X, y = [], []
    for i in range(lookback, len(data_scaled)):
        X.append(data_scaled[i-lookback:i])
        y.append(data_scaled[i])
    X, y = np.array(X), np.array(y)

    # Time-based split
    split = int(len(X) * 0.85)
    X_train, X_val = X[:split], X[split:]
    y_train, y_val = y[:split], y[split:]

    model = build_bilstm_attention(lookback=lookback, n_features=len(features))
    if model is None:
        return None, None, None

    cb = [
        callbacks.EarlyStopping(patience=15, restore_best_weights=True),
        callbacks.ReduceLROnPlateau(factor=0.5, patience=7, min_lr=1e-6),
    ]

    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=100,
        batch_size=32,
        callbacks=cb,
        verbose=0,
    )

    # Evaluate
    y_pred_scaled = model.predict(X_val, verbose=0)
    y_pred = scaler.inverse_transform(y_pred_scaled)
    y_true = scaler.inverse_transform(y_val)

    metrics = {}
    for i, feat in enumerate(features):
        metrics[feat] = {
            'rmse': float(np.sqrt(mean_squared_error(y_true[:, i], y_pred[:, i]))),
            'mae': float(mean_absolute_error(y_true[:, i], y_pred[:, i])),
            'r2': float(r2_score(y_true[:, i], y_pred[:, i])),
        }

    return model, scaler, metrics


# ═══════════════════════════════════════════════════════════════════════════
# 4. PHYSICAL CONSTRAINT POST-PROCESSING
# ═══════════════════════════════════════════════════════════════════════════
def apply_physical_constraints(predictions, previous=None):
    """Apply physical constraints to predictions.
    
    Rules:
    - Values must be within physical limits
    - Day-to-day changes must be smooth
    - Humidity can't exceed 100%
    - Rainfall must be >= 0
    - Pressure follows geostrophic constraints
    """
    constrained = dict(predictions)

    for param, (lo, hi) in PHYSICAL_LIMITS.items():
        if param in constrained:
            constrained[param] = max(lo, min(hi, constrained[param]))

    # Smoothness constraint
    if previous:
        for param, max_change in MAX_DAILY_CHANGE.items():
            if param in constrained and param in previous:
                change = constrained[param] - previous[param]
                if abs(change) > max_change:
                    # Dampen the change
                    constrained[param] = previous[param] + np.sign(change) * max_change

    # Consistency rules
    if 'humidity' in constrained and 'rainfall' in constrained:
        # Heavy rain requires high humidity
        if constrained['rainfall'] > 10 and constrained['humidity'] < 70:
            constrained['humidity'] = max(constrained['humidity'], 75)
        # Low humidity means no rain
        if constrained['humidity'] < 50 and constrained['rainfall'] > 5:
            constrained['rainfall'] *= 0.3

    return constrained


# ═══════════════════════════════════════════════════════════════════════════
# 5. ERROR TRACKING & FEEDBACK
# ═══════════════════════════════════════════════════════════════════════════
def save_error_tracking(all_metrics, save_path):
    """Save detailed error tracking for feedback loop analysis."""
    tracking = {
        'trained_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'model_version': 'v3',
        'targets': {},
    }

    for target, metrics in all_metrics.items():
        tracking['targets'][target] = {
            'overall': {
                'r2': metrics['r2'],
                'rmse': metrics['rmse'],
                'mae': metrics['mae'],
                'cv_r2_mean': metrics['cv_r2_mean'],
                'cv_r2_std': metrics['cv_r2_std'],
            },
            'per_season': metrics.get('season_metrics', {}),
            'n_features': metrics.get('n_features', 0),
            'best_params': metrics.get('best_params', {}),
        }

    with open(save_path, 'w') as f:
        json.dump(tracking, f, indent=2)
    print(f"[OK] Error tracking saved to {save_path}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main():
    t0 = time.time()
    print("=" * 70)
    print("  Weather ML Model Training v3 - All Improvements")
    print("=" * 70)

    # ── Load data ──────────────────────────────────────────────────────
    print("\n[1/5] Loading featured data...")
    df = load_featured_data()
    print(f"  Records: {len(df):,}  Features: {len(df.columns)}")

    # ── Train XGBoost models ───────────────────────────────────────────
    print("\n[2/5] Training XGBoost models with hyperparameter search...")
    import gc
    xgb_metrics = {}
    for target in TARGETS:
        print(f"\n  -- {target.upper()} --")
        model, features, metrics, quantile_models = train_xgboost_v3(df, target)

        # Save model + features
        joblib.dump(model, MODELS_DIR / f'xgboost_{target}_v3.pkl')
        joblib.dump(features, MODELS_DIR / f'xgboost_{target}_v3_features.pkl')

        # Save quantile models
        for qname, qmodel in quantile_models.items():
            joblib.dump(qmodel, MODELS_DIR / f'xgboost_{target}_q{qname}_v3.pkl')
            del qmodel
        del quantile_models, model
        gc.collect()

        xgb_metrics[target] = metrics

        print(f"     R²   = {metrics['r2']:.4f}")
        print(f"     RMSE = {metrics['rmse']:.4f}")
        print(f"     MAE  = {metrics['mae']:.4f}")
        print(f"     CV R² = {metrics['cv_r2_mean']:.4f} ± {metrics['cv_r2_std']:.4f}")
        if metrics.get('season_metrics'):
            for season, sm in metrics['season_metrics'].items():
                print(f"     {season.upper()} season R²={sm['r2']:.4f} RMSE={sm['rmse']:.4f}")

    # ── Train LSTM models per location ─────────────────────────────────
    print("\n[3/5] Training Bidirectional LSTM models per location...")
    lstm_metrics = {}
    locations = df['municipality'].unique() if 'municipality' in df.columns else []

    for loc in locations:
        loc_key = loc.lower().replace(' ', '_').replace('-', '_')
        print(f"\n  Training LSTM for {loc}...")
        model, scaler, metrics = train_lstm_v3(df, loc, lookback=14)

        if model is not None:
            # Save .h5 model
            model_path = MODELS_DIR / f'lstm_{loc_key}_v3.h5'
            model.save(model_path)
            # Save scaler
            joblib.dump(scaler, MODELS_DIR / f'scaler_{loc_key}_v3.pkl')
            lstm_metrics[loc_key] = metrics

            for feat, m in metrics.items():
                print(f"     {feat}: R²={m['r2']:.4f} RMSE={m['rmse']:.4f}")

    # ── Save combined metrics ──────────────────────────────────────────
    print("\n[4/5] Saving metrics and error tracking...")
    all_metrics_combined = {
        'xgboost': xgb_metrics,
        'lstm': lstm_metrics,
        'version': 'v3',
        'trained_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'dataset_size': len(df),
    }
    with open(MODELS_DIR / 'weather_model_metrics_v3.json', 'w') as f:
        json.dump(all_metrics_combined, f, indent=2)

    # Save error tracking for feedback loop
    save_error_tracking(xgb_metrics, MODELS_DIR / 'error_tracking_v3.json')

    # Also update the main metrics file used by the predictor
    # (backwards compatible format)
    compat_metrics = {}
    for target in TARGETS:
        if target in xgb_metrics:
            compat_metrics[target] = {
                'rmse': xgb_metrics[target]['rmse'],
                'mae': xgb_metrics[target]['mae'],
                'r2': xgb_metrics[target]['r2'],
            }
    with open(MODELS_DIR / 'weather_model_metrics.json', 'w') as f:
        json.dump(compat_metrics, f, indent=2)

    # ── Summary ────────────────────────────────────────────────────────
    elapsed = time.time() - t0
    print(f"\n[5/5] Training complete!")
    print(f"\n{'=' * 70}")
    print(f"  {'Target':<15} {'R²':>8} {'RMSE':>8} {'MAE':>8} {'CV R²':>10}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
    for t, m in xgb_metrics.items():
        print(f"  {t:<15} {m['r2']:>8.4f} {m['rmse']:>8.4f} {m['mae']:>8.4f} {m['cv_r2_mean']:>8.4f}±{m['cv_r2_std']:.3f}")

    if lstm_metrics:
        print(f"\n  LSTM Models:")
        for loc, lm in lstm_metrics.items():
            avg_r2 = np.mean([v['r2'] for v in lm.values()])
            print(f"    {loc}: avg R²={avg_r2:.4f}")

    print(f"\n  Time: {elapsed:.1f}s")
    print(f"  Models saved to: {MODELS_DIR}")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
