"""
Train Advanced ML Models: LSTM, Prophet, XGBoost for Weather Forecasting
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import xgboost as xgb
from prophet import Prophet
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import warnings
warnings.filterwarnings('ignore')

def prepare_lstm_data(df, location_filter=None, lookback=7, features=['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']):
    """Prepare data for LSTM model"""
    if location_filter:
        df = df[
            (df['municipality'].str.contains(location_filter, case=False, na=False)) |
            (df['province'].str.contains(location_filter, case=False, na=False))
        ]
    
    df = df.sort_values('date')
    data = df[features].values
    
    X, y = [], []
    for i in range(lookback, len(data)):
        X.append(data[i-lookback:i])
        y.append(data[i])
    
    return np.array(X), np.array(y)

def build_lstm_model(lookback=7, n_features=5):
    """Build LSTM neural network"""
    model = keras.Sequential([
        layers.LSTM(128, activation='relu', return_sequences=True, input_shape=(lookback, n_features)),
        layers.Dropout(0.2),
        layers.LSTM(64, activation='relu', return_sequences=True),
        layers.Dropout(0.2),
        layers.LSTM(32, activation='relu'),
        layers.Dropout(0.2),
        layers.Dense(16, activation='relu'),
        layers.Dense(n_features)
    ])
    
    model.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return model

def train_lstm_models(df, output_dir):
    """Train LSTM models for weather prediction"""
    print("🧠 Training LSTM Models...")
    
    models_dict = {}
    scalers_dict = {}
    
    # Train for key locations
    key_locations = ['Calapan', 'Oriental Mindoro', 'Pinamalayan', 'Bacolod', 'San Carlos']
    
    features = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
    
    for location in key_locations:
        print(f"\n📍 Training LSTM for {location}...")
        
        try:
            X, y = prepare_lstm_data(df, location_filter=location, lookback=7, features=features)
            
            if len(X) < 100:
                print(f"⚠️ Not enough data for {location}, skipping...")
                continue
            
            # Scale data
            scaler = StandardScaler()
            X_reshaped = X.reshape(-1, len(features))
            X_scaled = scaler.fit_transform(X_reshaped).reshape(X.shape)
            y_scaled = scaler.transform(y)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X_scaled, y_scaled, test_size=0.2, random_state=42)
            
            # Build and train model
            model = build_lstm_model(lookback=7, n_features=len(features))
            
            early_stopping = keras.callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
            
            model.fit(
                X_train, y_train,
                validation_data=(X_test, y_test),
                epochs=50,
                batch_size=32,
                callbacks=[early_stopping],
                verbose=0
            )
            
            # Evaluate
            test_loss, test_mae = model.evaluate(X_test, y_test, verbose=0)
            print(f"✅ Test MAE: {test_mae:.3f}")
            
            # Save model and scaler
            model_path = output_dir / f'lstm_{location.lower().replace(" ", "_")}.h5'
            model.save(model_path)
            models_dict[location] = str(model_path)
            
            scaler_path = output_dir / f'scaler_{location.lower().replace(" ", "_")}.pkl'
            joblib.dump(scaler, scaler_path)
            scalers_dict[location] = str(scaler_path)
            
            print(f"💾 Saved model to {model_path}")
            
        except Exception as e:
            print(f"❌ Error training LSTM for {location}: {e}")
    
    # Save model paths
    joblib.dump(models_dict, output_dir / 'lstm_models_registry.pkl')
    joblib.dump(scalers_dict, output_dir / 'lstm_scalers_registry.pkl')
    
    return models_dict, scalers_dict

def train_xgboost_models(df, output_dir):
    """Train XGBoost models for each weather parameter"""
    print("\n🌲 Training XGBoost Models...")
    
    # Select features for training
    feature_cols = [col for col in df.columns if col not in [
        'date', 'province', 'municipality', 'condition', 'month_day'
    ]]
    
    target_cols = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
    
    models = {}
    
    for target in target_cols:
        print(f"\nTraining XGBoost for {target}...")
        
        # Prepare data
        X = df[feature_cols].select_dtypes(include=[np.number])
        y = df[target]
        
        # Remove target from features if present
        if target in X.columns:
            X = X.drop(columns=[target])
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Train model
        model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42
        )
        
        model.fit(X_train, y_train, verbose=False)
        
        # Evaluate
        train_score = model.score(X_train, y_train)
        test_score = model.score(X_test, y_test)
        
        print(f"✅ Train R²: {train_score:.3f}, Test R²: {test_score:.3f}")
        
        # Save model
        model_path = output_dir / f'xgboost_{target}.pkl'
        joblib.dump(model, model_path)
        models[target] = model
        
        print(f"💾 Saved model to {model_path}")
    
    return models

def train_prophet_models(df, output_dir):
    """Train Prophet models for temperature forecasting"""
    print("\n📈 Training Prophet Models...")
    
    # Train for key locations
    key_locations = ['Calapan', 'Oriental Mindoro', 'Pinamalayan']
    
    models = {}
    
    for location in key_locations:
        print(f"\nTraining Prophet for {location}...")
        
        try:
            # Filter data
            loc_df = df[
                (df['municipality'].str.contains(location, case=False, na=False)) |
                (df['province'].str.contains(location, case=False, na=False))
            ].copy()
            
            if len(loc_df) < 30:
                print(f"⚠️ Not enough data for {location}, skipping...")
                continue
            
            # Prepare data for Prophet
            prophet_df = loc_df[['date', 'temperature']].rename(columns={'date': 'ds', 'temperature': 'y'})
            prophet_df = prophet_df.groupby('ds').mean().reset_index()
            
            # Train model
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                changepoint_prior_scale=0.05
            )
            
            model.fit(prophet_df)
            
            print(f"✅ Prophet model trained for {location}")
            
            # Save model
            model_path = output_dir / f'prophet_{location.lower().replace(" ", "_")}.pkl'
            joblib.dump(model, model_path)
            models[location] = model
            
            print(f"💾 Saved model to {model_path}")
            
        except Exception as e:
            print(f"❌ Error training Prophet for {location}: {e}")
    
    return models

def main():
    """Main training function"""
    print("🚀 Starting Advanced Model Training...")
    
    # Paths
    dataset_dir = Path(__file__).parent.parent
    input_file = dataset_dir / 'data' / 'philippines_weather_featured.csv'
    models_dir = dataset_dir / 'models'
    models_dir.mkdir(exist_ok=True)
    
    # Load engineered dataset
    print(f"\n📂 Loading {input_file}...")
    df = pd.read_csv(input_file, parse_dates=['date'])
    print(f"✅ Loaded {len(df)} records with {len(df.columns)} features")
    
    # Train models
    lstm_models, lstm_scalers = train_lstm_models(df, models_dir)
    xgboost_models = train_xgboost_models(df, models_dir)
    prophet_models = train_prophet_models(df, models_dir)
    
    print("\n" + "="*50)
    print("✅ ALL MODELS TRAINED SUCCESSFULLY!")
    print("="*50)
    print(f"📊 LSTM models: {len(lstm_models)}")
    print(f"📊 XGBoost models: {len(xgboost_models)}")
    print(f"📊 Prophet models: {len(prophet_models)}")

if __name__ == "__main__":
    main()
