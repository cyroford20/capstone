import pandas as pd
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
import joblib
import os
from pathlib import Path

class WeatherModelTrainer:
    def __init__(self):
        self.data_path = Path(__file__).parent.parent / 'data' / 'philippines_weather_raw.csv'
        self.models_dir = Path(__file__).parent.parent / 'models'
        self.models_dir.mkdir(exist_ok=True)

    def load_and_preprocess_data(self):
        """Load and preprocess the weather data"""
        df = pd.read_csv(self.data_path)
        df['date'] = pd.to_datetime(df['date'])

        # Group by date and take mean for numerical columns
        # For weather_condition, take the most common
        numerical_cols = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
        df_daily = df.groupby('date')[numerical_cols].mean().reset_index()

        # For weather_condition, get mode
        condition_mode = df.groupby('date')['weather_condition'].agg(lambda x: x.mode().iloc[0] if not x.mode().empty else 'Sunny').reset_index()
        df_daily = df_daily.merge(condition_mode, on='date')

        # Sort by date
        df_daily = df_daily.sort_values('date')

        return df_daily

    def train_arima_model(self, data, column, order=(5,1,0)):
        """Train ARIMA model for a time series"""
        try:
            model = ARIMA(data, order=order)
            model_fit = model.fit()
            return model_fit
        except:
            # Fallback to simple linear regression
            return self.train_linear_model(data, column)

    def train_linear_model(self, data, column):
        """Fallback linear regression model"""
        # Create lagged features
        df = pd.DataFrame({'value': data})
        for i in range(1, 8):  # 7 days lag
            df[f'lag_{i}'] = df['value'].shift(i)

        df = df.dropna()

        if len(df) < 10:
            return None

        X = df.drop('value', axis=1)
        y = df['value']

        model = LinearRegression()
        model.fit(X, y)
        return model

    def train_condition_classifier(self, conditions):
        """Train classifier for weather conditions"""
        # Encode conditions
        le = LabelEncoder()
        encoded_conditions = le.fit_transform(conditions)

        # Create features from previous conditions
        df = pd.DataFrame({'condition': encoded_conditions})
        for i in range(1, 4):  # 3 days lag
            df[f'lag_{i}'] = df['condition'].shift(i)

        df = df.dropna()

        if len(df) < 10:
            return None, le

        X = df.drop('condition', axis=1)
        y = df['condition']

        model = LinearRegression()  # Simple regression for encoded values
        model.fit(X, y)
        return model, le

    def train_models(self):
        """Train all weather prediction models"""
        print("Loading and preprocessing data...")
        df = self.load_and_preprocess_data()

        models = {}

        # Train numerical models
        numerical_cols = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']

        for col in numerical_cols:
            print(f"Training model for {col}...")
            data = df[col].values
            model = self.train_arima_model(data, col)
            if model:
                models[col] = model
                joblib.dump(model, self.models_dir / f'{col}_model.pkl')
                print(f"✅ Saved {col} model")
            else:
                print(f"❌ Failed to train {col} model")

        # Train condition classifier
        print("Training weather condition model...")
        condition_model, label_encoder = self.train_condition_classifier(df['weather_condition'].values)
        if condition_model:
            models['condition'] = condition_model
            models['condition_encoder'] = label_encoder
            joblib.dump(condition_model, self.models_dir / 'condition_model.pkl')
            joblib.dump(label_encoder, self.models_dir / 'condition_encoder.pkl')
            print("✅ Saved condition model")
        else:
            print("❌ Failed to train condition model")

        # Save last known values for prediction
        last_data = df.iloc[-1]
        models['last_data'] = {
            'date': last_data['date'],
            'temperature': last_data['temperature'],
            'humidity': last_data['humidity'],
            'rainfall': last_data['rainfall'],
            'wind_speed': last_data['wind_speed'],
            'pressure': last_data['pressure'],
            'condition': last_data['weather_condition']
        }
        joblib.dump(models['last_data'], self.models_dir / 'last_data.pkl')

        print("🎉 All models trained and saved!")
        return models

if __name__ == "__main__":
    trainer = WeatherModelTrainer()
    trainer.train_models()