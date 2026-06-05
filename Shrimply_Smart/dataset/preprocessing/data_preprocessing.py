"""Data audit and preprocessing utilities for the Philippines weather dataset.

This script performs:
- dataset audit (missing timestamps, duplicates, timezone issues)
- simple sensor drift detection (rolling mean shifts)
- imputation (forward/backward fill and rolling smoothing)
- outlier capping using IQR and domain rules
- saves preprocessing artifacts (imputer/scaler) and processed datasets
- creates an immutable time-based holdout split

Usage:
    python data_preprocessing.py

Outputs (under dataset/):
- philippines_weather_preprocessed.csv
- philippines_weather_holdout.csv
- preprocessing/ (folder with imputer and params)

"""
from pathlib import Path
import pandas as pd
import numpy as np
import json
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
import joblib
import warnings

ROOT = Path(__file__).resolve().parent.parent
RAW_FEATURED = ROOT / 'data' / 'philippines_weather_featured.csv'
OUT_PREPROCESSED = ROOT / 'data' / 'philippines_weather_preprocessed.csv'
OUT_HOLDOUT = ROOT / 'data' / 'philippines_weather_holdout.csv'
PREP_DIR = ROOT / 'preprocessing'
PREP_DIR.mkdir(exist_ok=True)

NUMERIC_COLS = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
DOMAIN_LIMITS = {
    'temperature': (-30, 60),
    'humidity': (0, 100),
    'rainfall': (0, 1000),
    'wind_speed': (0, 300),
    'pressure': (800, 1100),
}


def audit_dataset(df: pd.DataFrame):
    report = {}
    # basic shape
    report['rows'] = int(len(df))
    report['columns'] = list(df.columns)

    # check date parsing
    if 'date' in df.columns:
        report['date_nulls'] = int(df['date'].isna().sum())
        # range
        try:
            dmin = df['date'].min()
            dmax = df['date'].max()
            report['date_min'] = str(dmin)
            report['date_max'] = str(dmax)
        except Exception:
            report['date_min'] = None
            report['date_max'] = None

    # missing values per column
    report['missing_per_column'] = df.isna().sum().to_dict()

    # duplicate timestamps per location
    if 'municipality' in df.columns and 'date' in df.columns:
        dup_group = df.duplicated(subset=['municipality', 'date']).sum()
        report['duplicate_municipality_date_rows'] = int(dup_group)

    # timezone hint: check for naive vs timezone-aware strings (heuristic)
    # if dates are strings with +HH:MM present
    tz_like = df['date'].astype(str).str.contains(r"\+\d{2}:?\d{2}") if 'date' in df.columns else pd.Series(False)
    report['date_strings_with_tz'] = int(tz_like.sum())

    return report


def detect_sensor_drift(df: pd.DataFrame, window=30):
    """Detect sensor drift by looking at rolling mean changes per municipality."""
    drift_report = {}
    if 'municipality' not in df.columns:
        return drift_report

    for col in NUMERIC_COLS:
        if col not in df.columns:
            continue
        drift_report[col] = {}
        for mun, g in df.groupby('municipality'):
            series = g.sort_values('date')[col].dropna()
            if len(series) < window * 2:
                continue
            roll = series.rolling(window=window, min_periods=window).mean()
            # compare mean of first window and last window
            start_mean = roll.iloc[:window].mean()
            end_mean = roll.iloc[-window:].mean()
            change = None
            try:
                change = float(end_mean - start_mean)
            except Exception:
                change = None
            drift_report[col][mun] = {'start_mean': None if pd.isna(start_mean) else float(start_mean),
                                      'end_mean': None if pd.isna(end_mean) else float(end_mean),
                                      'change': change}
    return drift_report


def cap_outliers(df: pd.DataFrame, numeric_cols=NUMERIC_COLS):
    params = {}
    for col in numeric_cols:
        if col not in df.columns:
            continue
        ser = df[col]
        q1 = ser.quantile(0.25)
        q3 = ser.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        # also apply domain limits if present
        if col in DOMAIN_LIMITS:
            dlower, dupper = DOMAIN_LIMITS[col]
            lower = max(lower, dlower)
            upper = min(upper, dupper)
        params[col] = {'q1': float(q1), 'q3': float(q3), 'iqr': float(iqr), 'lower': float(lower), 'upper': float(upper)}
        df[col] = ser.clip(lower, upper)
    return df, params


def impute_dataframe(df: pd.DataFrame, numeric_cols=NUMERIC_COLS):
    # Ensure date is datetime
    df = df.sort_values('date').copy()
    # Forward fill then backward fill per municipality
    if 'municipality' in df.columns:
        # use transform to preserve original index and avoid MultiIndex issues
        for col in numeric_cols:
            if col in df.columns:
                df[col] = df.groupby('municipality')[col].transform(lambda s: s.ffill().bfill())
    else:
        df[numeric_cols] = df[numeric_cols].ffill().bfill()

    # For any remaining NaNs, fill with rolling mean per column
    for col in numeric_cols:
        if col not in df.columns:
            continue
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].rolling(7, min_periods=1).mean())

    # small smoothing: replace isolated NaNs with rolling median
    return df


def save_artifacts(scaler: StandardScaler = None, imputer: SimpleImputer = None, outlier_params=None):
    if scaler is not None:
        joblib.dump(scaler, PREP_DIR / 'feature_scaler.pkl')
    if imputer is not None:
        joblib.dump(imputer, PREP_DIR / 'imputer.pkl')
    if outlier_params is not None:
        with open(PREP_DIR / 'outlier_params.json', 'w') as f:
            json.dump(outlier_params, f, indent=2)


def create_holdout(df: pd.DataFrame, holdout_days=14):
    # create holdout as the final `holdout_days` per municipality or global tail
    df = df.sort_values('date').copy()
    if 'municipality' in df.columns:
        holdout_parts = []
        train_parts = []
        for mun, g in df.groupby('municipality'):
            if len(g) <= holdout_days:
                train_parts.append(g)
                continue
            hold = g.iloc[-holdout_days:]
            train = g.iloc[:-holdout_days]
            holdout_parts.append(hold)
            train_parts.append(train)
        train_df = pd.concat(train_parts).sort_values('date')
        hold_df = pd.concat(holdout_parts).sort_values('date') if holdout_parts else pd.DataFrame()
    else:
        hold_df = df.iloc[-holdout_days:]
        train_df = df.iloc[:-holdout_days]
    return train_df, hold_df


def main():
    warnings.filterwarnings('ignore')
    if not RAW_FEATURED.exists():
        print('Featured dataset not found at', RAW_FEATURED)
        return

    df = pd.read_csv(RAW_FEATURED, parse_dates=['date'], dayfirst=False)
    print('Loaded featured dataset with', len(df), 'rows')

    audit = audit_dataset(df)
    with open(PREP_DIR / 'audit_report.json', 'w') as f:
        json.dump(audit, f, indent=2)
    print('Saved audit report')

    drift = detect_sensor_drift(df)
    with open(PREP_DIR / 'drift_report.json', 'w') as f:
        json.dump(drift, f, indent=2)
    print('Saved drift report')

    # Cap outliers
    df_capped, outlier_params = cap_outliers(df)
    save_artifacts(outlier_params=outlier_params)
    print('Capped outliers and saved params')

    # Impute
    df_imputed = impute_dataframe(df_capped)
    print('Imputed missing values')

    # Fit a scaler on numeric features (train portion after holdout split)
    train_df, hold_df = create_holdout(df_imputed, holdout_days=14)
    scaler = StandardScaler()
    scaler.fit(train_df[NUMERIC_COLS].values)
    save_artifacts(scaler=scaler)
    print('Fitted and saved feature scaler')

    # Save processed files
    df_imputed.to_csv(OUT_PREPROCESSED, index=False)
    hold_df.to_csv(OUT_HOLDOUT, index=False)
    print('Saved preprocessed dataset and holdout')


if __name__ == '__main__':
    main()
