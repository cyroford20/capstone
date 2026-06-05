"""
Specialized pressure model — same per-municipality pipeline as rainfall_final.
"""
import numpy as np, pandas as pd, xgboost as xgb, joblib, json
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from pathlib import Path
import warnings; warnings.filterwarnings('ignore')

ROOT = Path(__file__).parent.parent
DATA = ROOT / 'data' / 'philippines_weather_raw.csv'
MODELS = ROOT / 'models'

def build(df):
    recs = []
    for m, g in df.groupby('municipality'):
        g = g.sort_values('date').reset_index(drop=True).copy()
        for c in ['temperature','humidity','rainfall','wind_speed','pressure']:
            for lag in [1,2,3,5,7]:
                g[f'{c}_lag{lag}'] = g[c].shift(lag)
            g[f'{c}_roll3']  = g[c].rolling(3,min_periods=1).mean()
            g[f'{c}_roll7']  = g[c].rolling(7,min_periods=1).mean()
            g[f'{c}_roll14'] = g[c].rolling(14,min_periods=1).mean()
            g[f'{c}_std7']   = g[c].rolling(7,min_periods=1).std()
        # pressure-specific
        g['pressure_diff1'] = g['pressure'].diff(1)
        g['pressure_diff3'] = g['pressure'].diff(3)
        g['pressure_ewm7']  = g['pressure'].ewm(span=7,min_periods=1).mean()
        g['pressure_ewm14'] = g['pressure'].ewm(span=14,min_periods=1).mean()
        # interactions
        g['humidity_sq']     = g['humidity']**2
        g['temp_humidity']   = g['temperature']*g['humidity']
        g['pressure_wind']   = g['pressure']*g['wind_speed']
        g['dew_point']       = g['temperature'] - ((100-g['humidity'])/5)
        # date
        g['day_sin']  = np.sin(2*np.pi*g['date'].dt.dayofyear/365)
        g['day_cos']  = np.cos(2*np.pi*g['date'].dt.dayofyear/365)
        g['month_sin']= np.sin(2*np.pi*g['date'].dt.month/12)
        g['month_cos']= np.cos(2*np.pi*g['date'].dt.month/12)
        g['is_wet_season']   = g['date'].dt.month.isin([6,7,8,9,10,11]).astype(int)
        g['is_amihan']       = g['date'].dt.month.isin([10,11,12,1,2,3]).astype(int)
        g['is_habagat']      = g['date'].dt.month.isin([6,7,8,9]).astype(int)
        recs.append(g)
    return pd.concat(recs,ignore_index=True).dropna().reset_index(drop=True)

raw = pd.read_csv(DATA, parse_dates=['date'])
daily = raw.groupby(['date','municipality'])[['temperature','humidity','rainfall','wind_speed','pressure']].mean().reset_index()
df = build(daily)
exclude = {'date','municipality','pressure','day_of_year','month'}
feats = [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude]
X, y = df[feats].values, df['pressure'].values
split = int(len(X)*0.8)
model = xgb.XGBRegressor(n_estimators=1200, max_depth=7, learning_rate=0.02,
    subsample=0.8, colsample_bytree=0.7, reg_alpha=0.5, reg_lambda=3.0,
    min_child_weight=5, gamma=0.1, random_state=42, verbosity=0, tree_method='hist')
model.fit(X[:split], y[:split], eval_set=[(X[split:], y[split:])], verbose=False)
yp = model.predict(X[split:])
r2 = r2_score(y[split:], yp)
rmse = np.sqrt(mean_squared_error(y[split:], yp))
mae = mean_absolute_error(y[split:], yp)
cv = cross_val_score(model, X, y, cv=TimeSeriesSplit(5), scoring='r2')
print(f"PRESSURE: R²={r2:.4f}  RMSE={rmse:.4f}  MAE={mae:.4f}  CV={cv.mean():.4f}±{cv.std():.4f}")
joblib.dump(model, MODELS/'xgboost_pressure.pkl')
joblib.dump(feats, MODELS/'xgboost_pressure_features.pkl')
# update metrics
mp = MODELS/'weather_model_metrics.json'
m = json.load(open(mp)) if mp.exists() else {}
m['pressure'] = {'r2':float(r2),'rmse':float(rmse),'mae':float(mae),'cv_r2_mean':float(cv.mean()),'cv_r2_std':float(cv.std())}
json.dump(m, open(mp,'w'), indent=2)
print(f"Saved {len(feats)} features")
