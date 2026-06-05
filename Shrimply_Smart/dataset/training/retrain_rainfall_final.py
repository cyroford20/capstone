"""
Specialized rainfall model — per-municipality training with lag-centric features.
Rainfall has 0.985 autocorrelation at lag1, so lag-based model should be strong.
"""
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
import joblib, json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

ROOT = Path(__file__).parent.parent
DATA_PATH = ROOT / 'data' / 'philippines_weather_raw.csv'
MODELS_DIR = ROOT / 'models'


def build_features(df):
    """Build features per municipality, sorted by date."""
    records = []
    for muni, gdf in df.groupby('municipality'):
        g = gdf.sort_values('date').reset_index(drop=True).copy()
        
        # Lag features for ALL weather variables
        for col in ['rainfall', 'temperature', 'humidity', 'wind_speed', 'pressure']:
            for lag in [1, 2, 3, 5, 7]:
                g[f'{col}_lag{lag}'] = g[col].shift(lag)
            # Rolling stats
            g[f'{col}_roll3'] = g[col].rolling(3, min_periods=1).mean()
            g[f'{col}_roll7'] = g[col].rolling(7, min_periods=1).mean()
            g[f'{col}_roll14'] = g[col].rolling(14, min_periods=1).mean()
            g[f'{col}_std7'] = g[col].rolling(7, min_periods=1).std()
        
        # Rainfall-specific features
        g['rainfall_roll3_max'] = g['rainfall'].rolling(3, min_periods=1).max()
        g['rainfall_roll7_max'] = g['rainfall'].rolling(7, min_periods=1).max()
        g['rainfall_diff1'] = g['rainfall'].diff(1)
        g['rainfall_diff3'] = g['rainfall'].diff(3)
        g['rainfall_ewm7'] = g['rainfall'].ewm(span=7, min_periods=1).mean()
        g['rainfall_ewm14'] = g['rainfall'].ewm(span=14, min_periods=1).mean()
        
        # Cross-variable interactions
        g['humidity_sq'] = g['humidity'] ** 2
        g['temp_humidity'] = g['temperature'] * g['humidity']
        g['pressure_wind'] = g['pressure'] * g['wind_speed']
        g['dew_point'] = g['temperature'] - ((100 - g['humidity']) / 5)
        g['pressure_drop_1d'] = g['pressure'].diff(1)
        g['pressure_drop_3d'] = g['pressure'].diff(3)
        g['humidity_rise_1d'] = g['humidity'].diff(1)
        
        # Cyclical date features
        g['day_of_year'] = g['date'].dt.dayofyear
        g['month'] = g['date'].dt.month
        g['day_sin'] = np.sin(2 * np.pi * g['day_of_year'] / 365)
        g['day_cos'] = np.cos(2 * np.pi * g['day_of_year'] / 365)
        g['month_sin'] = np.sin(2 * np.pi * g['month'] / 12)
        g['month_cos'] = np.cos(2 * np.pi * g['month'] / 12)
        
        # Seasonal flags
        g['is_wet_season'] = g['month'].isin([6, 7, 8, 9, 10, 11]).astype(int)
        g['is_typhoon_peak'] = g['month'].isin([8, 9, 10]).astype(int)
        g['is_habagat'] = g['month'].isin([6, 7, 8, 9]).astype(int)
        
        records.append(g)
    
    full = pd.concat(records, ignore_index=True)
    full = full.dropna().reset_index(drop=True)
    return full


def main():
    print("=" * 60)
    print("  Specialized Rainfall Model (lag-centric)")
    print("=" * 60)
    
    # Load and aggregate to daily per municipality
    raw = pd.read_csv(DATA_PATH, parse_dates=['date'])
    numeric = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
    daily = raw.groupby(['date', 'municipality'])[numeric].mean().reset_index()
    
    df = build_features(daily)
    print(f"  Records: {len(df)}, Features: {len(df.columns)}")
    
    # Features exclude raw targets and non-numeric
    exclude = {'date', 'municipality', 'rainfall', 'day_of_year', 'month'}
    features = [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude]
    print(f"  Model features: {len(features)}")
    
    X = df[features].values
    y = df['rainfall'].values
    
    # Time-based split
    split = int(len(X) * 0.8)
    X_tr, X_te = X[:split], X[split:]
    y_tr, y_te = y[:split], y[split:]
    
    print(f"  Train: {len(X_tr)}, Test: {len(X_te)}")
    
    # XGBoost with tuned hyperparameters for rainfall
    model = xgb.XGBRegressor(
        n_estimators=1200,
        max_depth=7,
        learning_rate=0.02,
        subsample=0.8,
        colsample_bytree=0.7,
        reg_alpha=0.5,
        reg_lambda=3.0,
        min_child_weight=5,
        gamma=0.1,
        random_state=42,
        verbosity=0,
        tree_method='hist',
    )
    
    model.fit(
        X_tr, y_tr,
        eval_set=[(X_te, y_te)],
        verbose=False,
    )
    
    y_pred = model.predict(X_te)
    y_pred = np.clip(y_pred, 0, None)  # No negative rainfall
    
    rmse = np.sqrt(mean_squared_error(y_te, y_pred))
    mae = mean_absolute_error(y_te, y_pred)
    r2 = r2_score(y_te, y_pred)
    
    # Cross-validation
    tscv = TimeSeriesSplit(n_splits=5)
    cv = cross_val_score(model, X, y, cv=tscv, scoring='r2')
    
    print(f"\n  RAINFALL MODEL RESULTS:")
    print(f"     R²    = {r2:.4f}")
    print(f"     RMSE  = {rmse:.4f}")
    print(f"     MAE   = {mae:.4f}")
    print(f"     CV R² = {cv.mean():.4f} ± {cv.std():.4f}")
    
    # Feature importance (top 10)
    importance = model.feature_importances_
    top_idx = np.argsort(importance)[-10:][::-1]
    print(f"\n  Top 10 Features:")
    for i in top_idx:
        print(f"     {features[i]:30s}  {importance[i]:.4f}")
    
    # Save model and features
    joblib.dump(model, MODELS_DIR / 'xgboost_rainfall.pkl')
    joblib.dump(features, MODELS_DIR / 'xgboost_rainfall_features.pkl')
    
    # Update metrics
    metrics_path = MODELS_DIR / 'weather_model_metrics.json'
    if metrics_path.exists():
        with open(metrics_path) as f:
            all_m = json.load(f)
    else:
        all_m = {}
    all_m['rainfall'] = {
        'r2': float(r2), 'rmse': float(rmse), 'mae': float(mae),
        'cv_r2_mean': float(cv.mean()), 'cv_r2_std': float(cv.std()),
    }
    with open(metrics_path, 'w') as f:
        json.dump(all_m, f, indent=2)
    
    print(f"\n  ✅ Saved xgboost_rainfall.pkl")
    print("=" * 60)


if __name__ == '__main__':
    main()
