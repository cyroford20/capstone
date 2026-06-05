"""
Finish training: condition classifier + correction models + last_data.pkl
(Run after main training completed the 5 XGBoost targets.)
"""
import sys, os, json
import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

BASE = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE / 'dataset' / 'models'
FEATURED_CSV = BASE / 'dataset' / 'data' / 'philippines_weather_featured_v3.csv'

def main():
    print("[LOAD] Reading featured dataset...")
    daily = pd.read_csv(FEATURED_CSV)
    print(f"  Rows: {len(daily):,}, Cols: {daily.shape[1]}")

    # ---------- Condition Classifier ----------
    print("\n[1/3] Training Condition Classifier (RandomForest — fast)...")
    le = LabelEncoder()
    daily['condition_encoded'] = le.fit_transform(daily['weather_condition'])
    print(f"  Classes: {list(le.classes_)}")

    # Feature columns = all numeric except targets/identifiers
    exclude = {'date', 'country', 'province', 'municipality', 'weather_condition',
               'condition_encoded', 'season', 'Unnamed: 0'}
    feat_cols = [c for c in daily.columns if c not in exclude and daily[c].dtype in [np.float64, np.float32, np.int64, np.int32, np.float16]]
    print(f"  Features: {len(feat_cols)}")

    X = daily[feat_cols].values.astype(np.float32)
    y = daily['condition_encoded'].values

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.1, random_state=42)

    clf = RandomForestClassifier(
        n_estimators=300, max_depth=12, random_state=42, n_jobs=-1,
    )
    clf.fit(X_train, y_train)
    acc = accuracy_score(y_test, clf.predict(X_test))
    print(f"  Condition accuracy: {acc:.4f}")

    joblib.dump(clf, MODELS_DIR / 'condition_model.pkl')
    joblib.dump(le, MODELS_DIR / 'condition_encoder.pkl')
    print("  Saved condition_model.pkl + condition_encoder.pkl")

    # ---------- Correction Models ----------
    print("\n[2/3] Training Correction Models (RandomForest)...")
    targets = ['temperature', 'humidity', 'pressure', 'wind_speed']

    # Simulate OpenWeather = actual + small noise
    for p in targets:
        noise = np.random.normal(0, daily[p].std() * 0.1, len(daily))
        daily[f'ow_{p}'] = daily[p] + noise

    ow_features = ['ow_temperature', 'ow_humidity', 'ow_pressure', 'ow_wind_speed']

    for param in targets:
        X_ow = daily[ow_features].values
        # Add visibility=10, clouds=50 (what the predictor sends)
        X_full = np.column_stack([X_ow, np.full(len(X_ow), 10.0), np.full(len(X_ow), 50.0)])
        y_corr = daily[param].values

        model = RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1)
        model.fit(X_full, y_corr)
        mae = np.mean(np.abs(y_corr - model.predict(X_full)))

        fname = f'correction_{param}_model.pkl'
        joblib.dump(model, MODELS_DIR / fname)
        print(f"  {param}: MAE={mae:.4f} -> Saved {fname}")

    correction_features = ['temperature', 'humidity', 'pressure', 'wind_speed', 'visibility', 'clouds']
    joblib.dump(correction_features, MODELS_DIR / 'correction_features.pkl')
    print("  Saved correction_features.pkl")

    # ---------- last_data.pkl ----------
    print("\n[3/3] Saving last_data.pkl...")
    last = daily.iloc[-1]
    last_data = {
        'temperature': float(last['temperature']),
        'humidity': float(last['humidity']),
        'rainfall': float(last['rainfall']),
        'wind_speed': float(last['wind_speed']),
        'pressure': float(last['pressure']),
        'condition': str(last['weather_condition']),
    }
    joblib.dump(last_data, MODELS_DIR / 'last_data.pkl')
    print(f"  last_data: {last_data}")

    # Update metrics file
    metrics_path = MODELS_DIR / 'weather_model_metrics.json'
    if metrics_path.exists():
        with open(metrics_path) as f:
            metrics = json.load(f)
    else:
        metrics = {}
    metrics['condition'] = {'accuracy': float(acc)}
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"\n  Updated metrics: {metrics_path}")

    print("\n[DONE] All remaining models trained and saved!")
    print(f"  Models directory: {MODELS_DIR}")

if __name__ == '__main__':
    main()
