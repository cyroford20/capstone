"""
Retrain Weather ML Models with Accuracy Metrics
================================================
Retrains XGBoost weather models on the 100K Philippines dataset with
walk-forward cross-validation, prints R²/RMSE/MAE for each target,
and saves a metrics report.
"""

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score, TimeSeriesSplit
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.preprocessing import StandardScaler
import joblib
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / 'data' / 'philippines_weather_raw.csv'
FEATURED_PATH = ROOT / 'data' / 'philippines_weather_featured.csv'
MODELS_DIR = ROOT / 'models'
MODELS_DIR.mkdir(exist_ok=True)


def load_and_engineer(path):
    """Load raw data and create time-series features."""
    df = pd.read_csv(path, parse_dates=['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Aggregate to daily per-municipality means
    numeric_cols = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
    daily = df.groupby(['date', 'province', 'municipality'])[numeric_cols].mean().reset_index()
    daily = daily.sort_values('date').reset_index(drop=True)

    # Date features
    daily['day_of_year'] = daily['date'].dt.dayofyear
    daily['month'] = daily['date'].dt.month
    daily['day_sin'] = np.sin(2 * np.pi * daily['day_of_year'] / 365)
    daily['day_cos'] = np.cos(2 * np.pi * daily['day_of_year'] / 365)
    daily['month_sin'] = np.sin(2 * np.pi * daily['month'] / 12)
    daily['month_cos'] = np.cos(2 * np.pi * daily['month'] / 12)

    # Seasonal flags
    daily['is_wet_season'] = daily['month'].isin([6, 7, 8, 9, 10, 11]).astype(int)
    daily['is_dry_season'] = 1 - daily['is_wet_season']
    daily['is_habagat'] = daily['month'].isin([6, 7, 8, 9]).astype(int)
    daily['is_amihan'] = daily['month'].isin([10, 11, 12, 1, 2, 3]).astype(int)

    # Lag features (previous day values)
    for col in numeric_cols:
        daily[f'{col}_lag1'] = daily.groupby('municipality')[col].shift(1)
        daily[f'{col}_lag3_avg'] = daily.groupby('municipality')[col].transform(lambda x: x.rolling(3, min_periods=1).mean())
        daily[f'{col}_lag7_avg'] = daily.groupby('municipality')[col].transform(lambda x: x.rolling(7, min_periods=1).mean())

    # Interaction features
    daily['temp_humidity'] = daily['temperature'] * daily['humidity']
    daily['pressure_wind'] = daily['pressure'] * daily['wind_speed']

    daily = daily.dropna().reset_index(drop=True)
    return daily


def train_xgboost_weather(df, target):
    """Train XGBoost for a single weather target with walk-forward CV."""
    exclude_cols = ['date', 'province', 'municipality', 'day_of_year', 'month']
    feature_cols = [c for c in df.select_dtypes(include=[np.number]).columns
                    if c not in exclude_cols and c != target]

    X = df[feature_cols].values
    y = df[target].values

    # Time-based split (last 20% for test)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    model = xgb.XGBRegressor(
        n_estimators=600,
        max_depth=7,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        verbosity=0,
        tree_method='hist',
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False,
    )

    y_pred = model.predict(X_test)

    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)

    # Cross-validation R²
    tscv = TimeSeriesSplit(n_splits=5)
    cv_scores = cross_val_score(model, X, y, cv=tscv, scoring='r2')

    return model, feature_cols, {
        'rmse': float(rmse),
        'mae': float(mae),
        'r2': float(r2),
        'cv_r2_mean': float(cv_scores.mean()),
        'cv_r2_std': float(cv_scores.std()),
    }


def main():
    print("=" * 60)
    print("  Weather ML Model Training — Philippines Dataset")
    print("=" * 60)

    print("\n[1/3] Loading & engineering features...")
    df = load_and_engineer(DATA_PATH)
    print(f"  Records: {len(df)}  Features: {len(df.columns)}")

    targets = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
    all_metrics = {}

    print("\n[2/3] Training XGBoost models...")
    for target in targets:
        print(f"\n  📊 {target.upper()}")
        model, features, metrics = train_xgboost_weather(df, target)

        # Save model
        joblib.dump(model, MODELS_DIR / f'xgboost_{target}.pkl')
        all_metrics[target] = metrics

        print(f"     R²     = {metrics['r2']:.4f}")
        print(f"     RMSE   = {metrics['rmse']:.4f}")
        print(f"     MAE    = {metrics['mae']:.4f}")
        print(f"     CV R²  = {metrics['cv_r2_mean']:.4f} ± {metrics['cv_r2_std']:.4f}")

    # Save feature list for inference
    joblib.dump(features, MODELS_DIR / 'weather_xgb_features.pkl')

    # Save metrics
    with open(MODELS_DIR / 'weather_model_metrics.json', 'w') as f:
        json.dump(all_metrics, f, indent=2)

    print("\n" + "=" * 60)
    print("  ✅ Weather Models Trained Successfully!")
    print("-" * 60)
    print(f"  {'Target':<15s} {'R²':>8s} {'RMSE':>8s} {'MAE':>8s}")
    print("-" * 60)
    for t, m in all_metrics.items():
        print(f"  {t:<15s} {m['r2']:>8.4f} {m['rmse']:>8.4f} {m['mae']:>8.4f}")
    print("=" * 60)


if __name__ == '__main__':
    main()
