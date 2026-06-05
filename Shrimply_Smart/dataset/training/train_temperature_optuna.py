"""Train temperature model with walk-forward CV and Optuna tuning.

Produces a tuned XGBoost model and saves scaler and artifacts to dataset/models/
"""
import os
import joblib
import optuna
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error
import xgboost as xgb
import json


ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / 'models'
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def create_features(df, lags=7):
    df = df.sort_values('date').copy()
    for lag in range(1, lags + 1):
        df[f'temp_lag_{lag}'] = df['temperature'].shift(lag)
    df['dayofyear'] = df['date'].dt.dayofyear
    df = df.dropna().reset_index(drop=True)
    return df


def walk_forward_split(df, n_splits=5, test_size=14):
    # yield train_idx, val_idx for each fold
    N = len(df)
    step = (N - test_size) // n_splits
    for i in range(n_splits):
        train_end = step * (i + 1)
        val_start = train_end
        val_end = val_start + test_size
        if val_end > N:
            val_end = N
        yield (np.arange(0, train_end), np.arange(val_start, val_end))


def objective(trial, X, y):
    params = {
        'tree_method': 'hist',
        'learning_rate': trial.suggest_loguniform('learning_rate', 0.01, 0.3),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'subsample': trial.suggest_float('subsample', 0.5, 1.0),
        'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
        'n_estimators': 500,
        'random_state': 42,
        'verbosity': 0,
    }

    rmses = []
    for train_idx, val_idx in walk_forward_split(pd.DataFrame(X), n_splits=4, test_size=14):
        X_train, y_train = X[train_idx], y[train_idx]
        X_val, y_val = X[val_idx], y[val_idx]
        dtrain = xgb.DMatrix(X_train, label=y_train)
        dval = xgb.DMatrix(X_val, label=y_val)
        evallist = [(dval, 'eval')]
        model = xgb.train(params, dtrain, num_boost_round=1000, evals=evallist,
                          early_stopping_rounds=30, verbose_eval=False)
        preds = model.predict(dval)
        rmses.append(np.sqrt(mean_squared_error(y_val, preds)))

    return float(np.mean(rmses))


def main():
    # Use featured dataset produced by feature_engineering.py
    df_path = ROOT / 'data' / 'philippines_weather_featured_v2.csv'
    if not df_path.exists():
        print('Featured dataset not found:', df_path)
        return
    df = pd.read_csv(df_path, parse_dates=['date'])

    # load feature columns metadata produced by feature_engineering
    feat_meta_path = ROOT / 'preprocessing' / 'feature_columns.json'
    if not feat_meta_path.exists():
        print('Feature metadata not found:', feat_meta_path)
        return
    meta = json.loads(open(feat_meta_path).read())
    # prefer numeric features for XGBoost training
    numeric_feature_cols = meta.get('numeric_columns', [])
    features = numeric_feature_cols

    # drop rows with any NA in selected features
    df = df.dropna(subset=features).reset_index(drop=True)

    X = df[features]
    y = df['temperature'].values

    # Load feature scaler v2 (fitted on training portion in preprocessing)
    scaler_path = ROOT / 'preprocessing' / 'feature_scaler_v2.pkl'
    if scaler_path.exists():
        scaler = joblib.load(scaler_path)
        # only scale numeric columns in the right order
        X_num = scaler.transform(X[numeric_feature_cols].values)
        # replace numeric columns with scaled values
        X_scaled = X.copy()
        X_scaled[numeric_feature_cols] = X_num
        X = X_scaled.values
        print('Loaded feature_scaler_v2 and applied to numeric features')
    else:
        # fallback: fit a new scaler on numeric columns
        scaler = StandardScaler()
        X_num = scaler.fit_transform(X[numeric_feature_cols].values)
        X_scaled = X.copy()
        X_scaled[numeric_feature_cols] = X_num
        X = X_scaled.values
        joblib.dump(scaler, MODELS_DIR / 'feature_scaler_v2_autofit.pkl')
        print('Fitted and saved fallback feature_scaler_v2_autofit')

    study = optuna.create_study(direction='minimize')
    func = lambda trial: objective(trial, X, y)
    # For interactive runs keep trials small; increase for full training
    study.optimize(func, n_trials=5)

    print('Best params:', study.best_params)

    # Train final model on full history with best params
    best = study.best_params
    params = {
        'tree_method': 'hist',
        'learning_rate': best['learning_rate'],
        'max_depth': best['max_depth'],
        'subsample': best['subsample'],
        'colsample_bytree': best['colsample_bytree'],
        'n_estimators': 1000,
        'random_state': 42,
        'verbosity': 0,
    }

    dtrain = xgb.DMatrix(X, label=y)
    model = xgb.train(params, dtrain, num_boost_round=500)
    joblib.dump(model, MODELS_DIR / 'temperature_model.pkl')
    print('Saved temperature_model.pkl')


if __name__ == '__main__':
    main()
