"""Generalized Optuna training script for multiple targets.

Usage:
    python dataset/train_optuna.py --target temperature --n_trials 5

This re-uses the featured dataset and preprocessing artifacts produced by
`feature_engineering.py` and `data_preprocessing.py`.
"""
import argparse
import json
from pathlib import Path
import joblib
import optuna

# Optional MLflow instrumentation. If mlflow is not installed the script
# will continue without experiment tracking.
try:
    import mlflow
    from optuna.integration import MLflowCallback
    _HAS_MLFLOW = True
except Exception:
    _HAS_MLFLOW = False
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error
import xgboost as xgb


ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / 'models'
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def walk_forward_split(df_len, n_splits=4, test_size=14):
    N = df_len
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
    for train_idx, val_idx in walk_forward_split(len(X), n_splits=4, test_size=14):
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=str, required=True,
                        help='Target column to train (e.g., temperature, humidity, rainfall)')
    parser.add_argument('--n_trials', type=int, default=5)
    parser.add_argument('--n_splits', type=int, default=4)
    parser.add_argument('--test_size', type=int, default=14)
    args = parser.parse_args()

    df_path = ROOT / 'data' / 'philippines_weather_featured_v2.csv'
    if not df_path.exists():
        raise SystemExit(f'Featured dataset not found: {df_path}')
    df = pd.read_csv(df_path, parse_dates=['date'])

    feat_meta_path = ROOT / 'preprocessing' / 'feature_columns.json'
    if not feat_meta_path.exists():
        raise SystemExit(f'Feature metadata not found: {feat_meta_path}')
    meta = json.loads(open(feat_meta_path).read())

    numeric_feature_cols = meta.get('numeric_columns', [])
    features = numeric_feature_cols

    if args.target not in df.columns:
        raise SystemExit(f'Target column "{args.target}" not found in dataset')

    # require non-null for selected features and target
    df = df.dropna(subset=features + [args.target]).reset_index(drop=True)

    X = df[features].copy()
    y = df[args.target].values

    # load or fallback scaler
    scaler_path = ROOT / 'preprocessing' / 'feature_scaler_v2.pkl'
    if scaler_path.exists():
        scaler = joblib.load(scaler_path)
        X_num = scaler.transform(X[numeric_feature_cols].values)
        X_scaled = X.copy()
        X_scaled[numeric_feature_cols] = X_num
        X = X_scaled.values
        print('Loaded feature_scaler_v2 and applied to numeric features')
    else:
        scaler = StandardScaler()
        X_num = scaler.fit_transform(X[numeric_feature_cols].values)
        X_scaled = X.copy()
        X_scaled[numeric_feature_cols] = X_num
        X = X_scaled.values
        joblib.dump(scaler, MODELS_DIR / f'feature_scaler_v2_autofit_{args.target}.pkl')
        print('Fitted and saved fallback feature_scaler_v2_autofit')

    study = optuna.create_study(direction='minimize')
    func = lambda trial: objective(trial, X, y)

    if _HAS_MLFLOW:
        mlruns_path = ROOT / 'mlruns'
        mlflow.set_tracking_uri(str(mlruns_path))
        mlflow.set_experiment(f'optuna_{args.target}')
        print(f'Logging Optuna runs to MLflow at: {mlruns_path}')
        # MLflowCallback will log each trial's params/metrics
        mlflow_cb = MLflowCallback(tracking_uri=str(mlruns_path), metric_name='rmse')
        with mlflow.start_run(run_name=f'optuna_{args.target}'):
            study.optimize(func, n_trials=args.n_trials, callbacks=[mlflow_cb])
    else:
        print('MLflow not available — running Optuna without MLflow tracking')
        study.optimize(func, n_trials=args.n_trials)

    print(f'Best params for {args.target}:', study.best_params)

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
    out_path = MODELS_DIR / f'{args.target}_model.pkl'
    joblib.dump(model, out_path)
    print(f'Saved {out_path}')

    # Log final artifacts to MLflow if available
    if _HAS_MLFLOW:
        # record best params and metric
        mlflow.log_params(study.best_params)
        mlflow.log_metric('best_rmse', float(study.best_value))
        # add the model file as an artifact so it appears in the run UI
        mlflow.log_artifact(str(out_path))
        # also save and log the scaler used (if present)
        if scaler_path.exists():
            mlflow.log_artifact(str(scaler_path))
        print('Logged artifacts to MLflow')


if __name__ == '__main__':
    main()
