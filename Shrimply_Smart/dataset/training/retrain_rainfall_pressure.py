"""
Retrain rainfall and pressure models with enhanced features / tuning.
"""
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
import joblib
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / 'data' / 'philippines_weather_raw.csv'
MODELS_DIR = ROOT / 'models'


def load_and_engineer_v2(path):
    """Enhanced feature engineering for rainfall/pressure."""
    df = pd.read_csv(path, parse_dates=['date']).sort_values('date').reset_index(drop=True)
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
    daily['week_of_year'] = daily['date'].dt.isocalendar().week.astype(int)
    daily['week_sin'] = np.sin(2 * np.pi * daily['week_of_year'] / 52)
    daily['week_cos'] = np.cos(2 * np.pi * daily['week_of_year'] / 52)

    # Seasonal
    daily['is_wet_season'] = daily['month'].isin([6, 7, 8, 9, 10, 11]).astype(int)
    daily['is_dry_season'] = 1 - daily['is_wet_season']
    daily['is_habagat'] = daily['month'].isin([6, 7, 8, 9]).astype(int)
    daily['is_amihan'] = daily['month'].isin([10, 11, 12, 1, 2, 3]).astype(int)
    daily['is_typhoon_peak'] = daily['month'].isin([8, 9, 10]).astype(int)

    # Lags — more aggresive for rainfall
    for col in numeric_cols:
        for lag in [1, 2, 3]:
            daily[f'{col}_lag{lag}'] = daily.groupby('municipality')[col].shift(lag)
        daily[f'{col}_roll3'] = daily.groupby('municipality')[col].transform(lambda x: x.rolling(3, min_periods=1).mean())
        daily[f'{col}_roll7'] = daily.groupby('municipality')[col].transform(lambda x: x.rolling(7, min_periods=1).mean())
        daily[f'{col}_roll14'] = daily.groupby('municipality')[col].transform(lambda x: x.rolling(14, min_periods=1).mean())
        daily[f'{col}_std7'] = daily.groupby('municipality')[col].transform(lambda x: x.rolling(7, min_periods=1).std())

    # Derived
    daily['humidity_sq'] = daily['humidity'] ** 2
    daily['temp_humidity'] = daily['temperature'] * daily['humidity']
    daily['pressure_wind'] = daily['pressure'] * daily['wind_speed']
    daily['dew_point_approx'] = daily['temperature'] - ((100 - daily['humidity']) / 5)
    daily['rain_yesterday'] = (daily.groupby('municipality')['rainfall'].shift(1) > 0).astype(int)
    daily['rain_3day_sum'] = daily.groupby('municipality')['rainfall'].transform(lambda x: x.rolling(3, min_periods=1).sum())

    daily = daily.dropna().reset_index(drop=True)
    return daily


def train_target(df, target, n_estimators=800, max_depth=8, lr=0.03):
    exclude = ['date', 'province', 'municipality', 'day_of_year', 'month', 'week_of_year']
    features = [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude and c != target]
    X = df[features].values
    y = df[target].values

    split = int(len(X) * 0.8)
    X_tr, X_te = X[:split], X[split:]
    y_tr, y_te = y[:split], y[split:]

    model = xgb.XGBRegressor(
        n_estimators=n_estimators, max_depth=max_depth, learning_rate=lr,
        subsample=0.85, colsample_bytree=0.8, reg_alpha=0.3, reg_lambda=2.0,
        random_state=42, verbosity=0, tree_method='hist',
    )
    model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=False)

    y_pred = model.predict(X_te)
    rmse = np.sqrt(mean_squared_error(y_te, y_pred))
    mae = mean_absolute_error(y_te, y_pred)
    r2 = r2_score(y_te, y_pred)
    tscv = TimeSeriesSplit(n_splits=5)
    cv = cross_val_score(model, X, y, cv=tscv, scoring='r2')

    return model, features, {'rmse': float(rmse), 'mae': float(mae), 'r2': float(r2),
                              'cv_r2_mean': float(cv.mean()), 'cv_r2_std': float(cv.std())}


def main():
    print("Enhanced Rainfall & Pressure Model Training")
    print("=" * 55)
    df = load_and_engineer_v2(DATA_PATH)
    print(f"Records: {len(df)}  Features: {len(df.columns)}")

    for target in ['rainfall', 'pressure']:
        print(f"\n  📊 {target.upper()}")
        model, feats, m = train_target(df, target)
        joblib.dump(model, MODELS_DIR / f'xgboost_{target}.pkl')
        print(f"     R²    = {m['r2']:.4f}")
        print(f"     RMSE  = {m['rmse']:.4f}")
        print(f"     MAE   = {m['mae']:.4f}")
        print(f"     CV R² = {m['cv_r2_mean']:.4f} ± {m['cv_r2_std']:.4f}")

    # Update metrics file
    metrics_path = MODELS_DIR / 'weather_model_metrics.json'
    if metrics_path.exists():
        with open(metrics_path) as f:
            all_m = json.load(f)
    else:
        all_m = {}

    for target in ['rainfall', 'pressure']:
        _, _, m = train_target(df, target)
        all_m[target] = m

    with open(metrics_path, 'w') as f:
        json.dump(all_m, f, indent=2)

    print("\n✅ Done — updated xgboost_rainfall.pkl & xgboost_pressure.pkl")


if __name__ == '__main__':
    main()
