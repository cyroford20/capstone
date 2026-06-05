"""
Retrain LSTM Models on 383K Featured Weather Dataset
This script trains location-specific LSTM models using the expanded featured dataset
to improve weather forecast accuracy for days 6-8 (ensemble predictions).
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, callbacks
import json
import time

def prepare_lstm_data(df, lookback=7, n_features=5):
    """Prepare data for LSTM with proper normalization"""
    features = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
    
    # Use only available features
    available_features = [f for f in features if f in df.columns]
    data = df[available_features].values
    
    X, y = [], []
    for i in range(lookback, len(data)):
        X.append(data[i-lookback:i])
        y.append(data[i])
    
    if len(X) == 0:
        return None, None, None
    
    return np.array(X), np.array(y), available_features

def normalize_lstm_data(X, y, scaler=None):
    """Normalize LSTM data to [0, 1] range"""
    if scaler is None:
        scaler = MinMaxScaler(feature_range=(0, 1))
        X_reshaped = X.reshape(-1, X.shape[-1])
        scaler.fit(X_reshaped)
    
    X_reshaped = X.reshape(-1, X.shape[-1])
    X_normalized = scaler.transform(X_reshaped).reshape(X.shape)
    y_normalized = scaler.transform(y)
    
    return X_normalized, y_normalized, scaler

def build_lstm_model(lookback=7, n_features=5):
    """Build improved LSTM architecture for weather prediction"""
    model = keras.Sequential([
        layers.LSTM(256, activation='relu', return_sequences=True, 
                   input_shape=(lookback, n_features),
                   kernel_regularizer=keras.regularizers.l2(0.001)),
        layers.Dropout(0.3),
        layers.LSTM(128, activation='relu', return_sequences=True,
                   kernel_regularizer=keras.regularizers.l2(0.001)),
        layers.Dropout(0.3),
        layers.LSTM(64, activation='relu', return_sequences=False,
                   kernel_regularizer=keras.regularizers.l2(0.001)),
        layers.Dropout(0.2),
        layers.Dense(32, activation='relu'),
        layers.Dropout(0.2),
        layers.Dense(16, activation='relu'),
        layers.Dense(n_features)
    ])
    
    opt = keras.optimizers.Adam(learning_rate=0.001)
    model.compile(optimizer=opt, loss='mse', metrics=['mae', 'mape'])
    
    return model

def train_lstm_for_location(df, location_name, output_dir, lookback=7):
    """Train LSTM for a specific location"""
    print(f"\n{'='*60}")
    print(f"Training LSTM for {location_name}")
    print(f"{'='*60}")
    
    # Get data for location (case-insensitive, either municipality or province)
    location_df = df[
        (df['municipality'].str.contains(location_name, case=False, na=False)) |
        (df['province'].str.contains(location_name, case=False, na=False))
    ].copy()
    
    location_df = location_df.sort_values('date').reset_index(drop=True)
    
    print(f"Records for {location_name}: {len(location_df)}")
    
    if len(location_df) < 100:
        print(f"⚠️  Insufficient data ({len(location_df)} < 100), skipping {location_name}")
        return None
    
    # Prepare data
    X, y, feature_names = prepare_lstm_data(location_df, lookback=lookback)
    
    if X is None:
        print(f"❌ Failed to prepare data for {location_name}")
        return None
    
    print(f"Samples: {len(X)}, Features: {len(feature_names)}, Lookback: {lookback}")
    print(f"Features: {feature_names}")
    
    # Normalize
    X_norm, y_norm, scaler = normalize_lstm_data(X, y)
    
    # Split: 80% train, 20% test
    split_idx = int(len(X_norm) * 0.8)
    X_train = X_norm[:split_idx]
    y_train = y_norm[:split_idx]
    X_test = X_norm[split_idx:]
    y_test = y_norm[split_idx:]
    
    print(f"Train samples: {len(X_train)}, Test samples: {len(X_test)}")
    
    # Build model
    model = build_lstm_model(lookback=lookback, n_features=len(feature_names))
    
    # Callbacks
    early_stopping = callbacks.EarlyStopping(
        monitor='val_loss',
        patience=15,
        restore_best_weights=True,
        verbose=1
    )
    
    reduce_lr = callbacks.ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.5,
        patience=5,
        min_lr=0.00001,
        verbose=1
    )
    
    # Train
    print("Training...")
    start_time = time.time()
    
    history = model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=100,
        batch_size=16,
        callbacks=[early_stopping, reduce_lr],
        verbose=1
    )
    
    elapsed = time.time() - start_time
    print(f"Training completed in {elapsed:.1f}s")
    
    # Evaluate
    train_loss, train_mae, train_mape = model.evaluate(X_train, y_train, verbose=0)
    test_loss, test_mae, test_mape = model.evaluate(X_test, y_test, verbose=0)
    
    print(f"\n📊 Metrics:")
    print(f"  Train Loss: {train_loss:.4f} | MAE: {train_mae:.4f} | MAPE: {train_mape:.2f}%")
    print(f"  Test Loss: {test_loss:.4f} | MAE: {test_mae:.4f} | MAPE: {test_mape:.2f}%")
    
    # Save model
    loc_key = location_name.lower().replace(' ', '_')
    model_path = output_dir / f'lstm_{loc_key}.h5'
    model.save(model_path, overwrite=True)
    print(f"✅ Model saved: {model_path}")
    
    # Save scaler
    scaler_path = output_dir / f'lstm_{loc_key}_scaler.pkl'
    joblib.dump(scaler, scaler_path)
    print(f"✅ Scaler saved: {scaler_path}")
    
    # Save feature names
    features_path = output_dir / f'lstm_{loc_key}_features.pkl'
    joblib.dump(feature_names, features_path)
    print(f"✅ Features saved: {features_path}")
    
    return {
        'location': location_name,
        'samples': len(X),
        'train_samples': len(X_train),
        'test_samples': len(X_test),
        'train_loss': float(train_loss),
        'train_mae': float(train_mae),
        'train_mape': float(train_mape),
        'test_loss': float(test_loss),
        'test_mae': float(test_mae),
        'test_mape': float(test_mape),
        'epochs': len(history.history['loss']),
        'model_path': str(model_path),
        'scaler_path': str(scaler_path),
        'features_path': str(features_path),
    }

def main():
    """Main training function"""
    print("\n" + "="*80)
    print("🧠  LSTM RETRAINING ON 383K FEATURED DATASET")
    print("="*80)
    
    # Paths
    dataset_dir = Path(__file__).parent.parent
    featured_file = dataset_dir / 'data' / 'philippines_weather_featured_v2.csv'
    models_dir = dataset_dir / 'models'
    models_dir.mkdir(exist_ok=True)
    
    # Load dataset
    print(f"\n📂 Loading featured dataset: {featured_file}")
    if not featured_file.exists():
        print(f"❌ File not found: {featured_file}")
        print("   Please ensure philippines_weather_featured_v2.csv exists")
        return
    
    df = pd.read_csv(featured_file, parse_dates=['date'] if 'date' in pd.read_csv(featured_file, nrows=1).columns else [])
    print(f"✅ Loaded {len(df):,} records with {len(df.columns)} columns")
    print(f"   Date range: {df['date'].min() if 'date' in df.columns else 'N/A'} to {df['date'].max() if 'date' in df.columns else 'N/A'}")
    
    # Key locations to train
    locations = ['Calapan', 'Oriental Mindoro', 'Pinamalayan', 'Bacolod', 'San Carlos']
    
    results = {
        'training_date': str(pd.Timestamp.now()),
        'dataset_size': len(df),
        'locations': {}
    }
    
    # Train for each location
    for location in locations:
        result = train_lstm_for_location(df, location, models_dir, lookback=7)
        if result:
            results['locations'][location] = result
    
    # Save results
    results_file = models_dir / 'lstm_retraining_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved: {results_file}")
    
    # Summary
    print("\n" + "="*80)
    print("📊  RETRAINING SUMMARY")
    print("="*80)
    print(f"Total locations trained: {len(results['locations'])}")
    for loc, metrics in results['locations'].items():
        print(f"\n{loc}:")
        print(f"  Samples: {metrics['samples']:,}")
        print(f"  Test MAE: {metrics['test_mae']:.4f}")
        print(f"  Test MAPE: {metrics['test_mape']:.2f}%")
        print(f"  Epochs: {metrics['epochs']}")
    
    print("\n✅ LSTM RETRAINING COMPLETE!")
    print("   New models will be used automatically by enhanced_weather_predictor.py")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
