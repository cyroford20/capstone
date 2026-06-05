"""
Advanced Feature Engineering for Weather Prediction
Adds seasonal patterns, lagged features, cyclical features, and moving averages
"""

import pandas as pd
import numpy as np
from pathlib import Path

def add_cyclical_features(df):
    """Add cyclical features using sin/cos transformations"""
    # Day of year (1-365)
    df['day_of_year'] = df['date'].dt.dayofyear
    df['day_sin'] = np.sin(2 * np.pi * df['day_of_year'] / 365)
    df['day_cos'] = np.cos(2 * np.pi * df['day_of_year'] / 365)
    
    # Month (1-12)
    df['month'] = df['date'].dt.month
    df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    
    return df

def add_seasonal_features(df):
    """Add seasonal indicators"""
    df['month'] = df['date'].dt.month
    
    # Philippine seasons
    # Dry season: November to April
    # Wet season: May to October
    df['is_wet_season'] = df['month'].apply(lambda x: 1 if 5 <= x <= 10 else 0)
    df['is_dry_season'] = 1 - df['is_wet_season']
    
    # Southwest Monsoon (Habagat): May-October
    # Northeast Monsoon (Amihan): November-April
    df['is_habagat'] = df['is_wet_season']
    df['is_amihan'] = df['is_dry_season']
    
    # Typhoon season: June-November
    df['is_typhoon_season'] = df['month'].apply(lambda x: 1 if 6 <= x <= 11 else 0)
    
    return df

def add_lagged_features(df, columns=['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure'], lags=[1, 3, 7]):
    """Add lagged features for time series prediction"""
    df = df.sort_values(['province', 'municipality', 'date'])
    
    for col in columns:
        if col in df.columns:
            for lag in lags:
                df[f'{col}_lag_{lag}'] = df.groupby(['province', 'municipality'])[col].shift(lag)
    
    return df

def add_moving_averages(df, columns=['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure'], windows=[3, 7, 14]):
    """Add rolling mean features"""
    df = df.sort_values(['province', 'municipality', 'date'])
    
    for col in columns:
        if col in df.columns:
            for window in windows:
                df[f'{col}_ma_{window}'] = df.groupby(['province', 'municipality'])[col].transform(
                    lambda x: x.rolling(window=window, min_periods=1).mean()
                )
                df[f'{col}_std_{window}'] = df.groupby(['province', 'municipality'])[col].transform(
                    lambda x: x.rolling(window=window, min_periods=1).std()
                )
    
    return df

def add_historical_averages(df):
    """Add historical averages for same date in previous years"""
    df['month_day'] = df['date'].dt.strftime('%m-%d')
    
    # Calculate historical averages by location and month-day
    historical_stats = df.groupby(['province', 'municipality', 'month_day']).agg({
        'temperature': ['mean', 'std'],
        'humidity': ['mean', 'std'],
        'rainfall': ['mean', 'sum'],
        'wind_speed': 'mean',
        'pressure': 'mean'
    }).reset_index()
    
    historical_stats.columns = ['_'.join(col).strip('_') for col in historical_stats.columns.values]
    historical_stats = historical_stats.rename(columns={'province': 'province', 'municipality': 'municipality', 'month_day': 'month_day'})
    
    # Merge back to main dataframe
    df = df.merge(
        historical_stats,
        on=['province', 'municipality', 'month_day'],
        how='left',
        suffixes=('', '_hist')
    )
    
    return df

def add_weather_extremes(df):
    """Add features for extreme weather conditions"""
    # Temperature extremes
    df['is_hot'] = (df['temperature'] > 32).astype(int)
    df['is_cold'] = (df['temperature'] < 22).astype(int)
    
    # Heavy rainfall
    df['is_heavy_rain'] = (df['rainfall'] > 10).astype(int)
    
    # High wind
    df['is_high_wind'] = (df['wind_speed'] > 20).astype(int)
    
    return df

def engineer_features(input_file='philippines_weather_raw.csv', output_file='philippines_weather_featured.csv'):
    """Main function to engineer all features"""
    print("🔧 Starting Advanced Feature Engineering...")
    
    # Load data
    df = pd.read_csv(input_file, parse_dates=['date'])
    print(f"✅ Loaded {len(df)} records")
    
    # Add all features
    print("Adding cyclical features...")
    df = add_cyclical_features(df)
    
    print("Adding seasonal features...")
    df = add_seasonal_features(df)
    
    print("Adding lagged features...")
    df = add_lagged_features(df)
    
    print("Adding moving averages...")
    df = add_moving_averages(df)
    
    print("Adding historical averages...")
    df = add_historical_averages(df)
    
    print("Adding weather extremes...")
    df = add_weather_extremes(df)
    
    # Drop rows with NaN from lagging (keep most recent data)
    initial_rows = len(df)
    df = df.dropna()
    print(f"Dropped {initial_rows - len(df)} rows with missing values from feature engineering")
    
    # Save engineered dataset
    df.to_csv(output_file, index=False)
    print(f"✅ Saved engineered dataset to {output_file}")
    print(f"📊 Final shape: {df.shape}")
    print(f"📋 Features: {list(df.columns)}")
    
    return df

if __name__ == "__main__":
    dataset_dir = Path(__file__).parent
    input_path = dataset_dir / 'philippines_weather_raw.csv'
    output_path = dataset_dir / 'philippines_weather_featured.csv'
    
    engineer_features(str(input_path), str(output_path))
