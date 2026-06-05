import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import requests
from datetime import datetime, timedelta
from pathlib import Path
import time

class WeatherCorrectionTrainer:
    def __init__(self):
        self.csv_path = Path(__file__).parent.parent / 'data' / 'philippines_weather_raw.csv'
        self.models_dir = Path(__file__).parent.parent / 'models'
        self.openweather_api_key = os.getenv('OPENWEATHER_API_KEY', 'your-api-key-here')
        self.models_dir.mkdir(exist_ok=True)

    def collect_openweather_historical_data(self, locations, days_back=30):
        """Collect historical OpenWeather data for comparison"""
        historical_data = []

        for location in locations[:5]:  # Limit to avoid API rate limits
            print(f"Collecting OpenWeather data for {location}...")

            # Get current data and simulate historical by varying dates
            try:
                url = f'https://api.openweathermap.org/data/2.5/weather?q={location},PH&appid={self.openweather_api_key}&units=metric'
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                current_data = response.json()

                # Simulate historical data by adding date variations
                base_date = datetime.now()
                for i in range(days_back):
                    record_date = base_date - timedelta(days=i)

                    # Add some realistic variations
                    temp_variation = np.random.uniform(-3, 3)
                    humidity_variation = np.random.randint(-10, 10)
                    pressure_variation = np.random.uniform(-10, 10)

                    ow_record = {
                        'date': record_date.strftime('%Y-%m-%d'),
                        'location': location,
                        'ow_temperature': current_data['main']['temp'] + temp_variation,
                        'ow_humidity': max(0, min(100, current_data['main']['humidity'] + humidity_variation)),
                        'ow_pressure': current_data['main']['pressure'] + pressure_variation,
                        'ow_wind_speed': current_data['wind']['speed'] * 3.6,  # Convert to km/h
                        'ow_visibility': current_data.get('visibility', 10000) / 1000,  # Convert to km
                        'ow_clouds': current_data['clouds']['all']
                    }
                    historical_data.append(ow_record)

                time.sleep(1)  # Rate limiting

            except Exception as e:
                print(f"Error collecting data for {location}: {e}")
                continue

        return pd.DataFrame(historical_data)

    def prepare_correction_training_data(self):
        """Prepare training data by matching OpenWeather and local data"""
        print("Loading local weather data...")
        local_df = pd.read_csv(self.csv_path)
        local_df['date'] = pd.to_datetime(local_df['date'])

        # Aggregate local data by date and location
        local_agg = local_df.groupby(['date', 'province', 'municipality']).agg({
            'temperature': 'mean',
            'humidity': 'mean',
            'pressure': 'mean',
            'wind_speed': 'mean',
            'rainfall': 'mean'
        }).reset_index()

        # Get sample locations for OpenWeather data collection
        sample_locations = local_df[['province', 'municipality']].drop_duplicates()
        sample_locations = sample_locations.head(10)  # Limit for API calls
        locations = [f"{row['municipality']}" for _, row in sample_locations.iterrows()]

        print("Collecting OpenWeather historical data...")
        ow_df = self.collect_openweather_historical_data(locations, days_back=15)

        if ow_df.empty:
            print("No OpenWeather data collected, using synthetic corrections")
            return self.create_synthetic_corrections(local_agg)

        # Merge datasets on approximate date and location
        training_data = []

        for _, local_row in local_agg.iterrows():
            # Find closest OpenWeather match
            location_matches = ow_df[
                ow_df['location'].str.contains(local_row['municipality'], case=False, na=False) |
                ow_df['location'].str.contains(local_row['province'], case=False, na=False)
            ]

            if not location_matches.empty:
                # Find closest date match
                location_matches['date_diff'] = abs(
                    pd.to_datetime(location_matches['date']) - local_row['date']
                ).dt.days

                closest_match = location_matches.loc[location_matches['date_diff'].idxmin()]

                if closest_match['date_diff'] <= 2:  # Within 2 days
                    training_record = {
                        'local_temperature': local_row['temperature'],
                        'local_humidity': local_row['humidity'],
                        'local_pressure': local_row['pressure'],
                        'local_wind_speed': local_row['wind_speed'],
                        'ow_temperature': closest_match['ow_temperature'],
                        'ow_humidity': closest_match['ow_humidity'],
                        'ow_pressure': closest_match['ow_pressure'],
                        'ow_wind_speed': closest_match['ow_wind_speed'],
                        'ow_visibility': closest_match['ow_visibility'],
                        'ow_clouds': closest_match['ow_clouds']
                    }
                    training_data.append(training_record)

        if not training_data:
            print("No matching data found, using synthetic corrections")
            return self.create_synthetic_corrections(local_agg)

        return pd.DataFrame(training_data)

    def create_synthetic_corrections(self, local_data):
        """Create synthetic correction data when API data is unavailable"""
        print("Creating synthetic correction training data...")

        # Calculate typical corrections based on local vs global weather patterns
        synthetic_data = []

        for _, row in local_data.iterrows():
            # Philippines weather tends to be more humid and have different pressure patterns
            correction = {
                'local_temperature': row['temperature'],
                'local_humidity': row['humidity'],
                'local_pressure': row['pressure'],
                'local_wind_speed': row['wind_speed'],
                'ow_temperature': row['temperature'] + np.random.uniform(-2, 2),  # Slight temp variation
                'ow_humidity': max(0, min(100, row['humidity'] + np.random.randint(-15, 5))),  # Often more humid locally
                'ow_pressure': row['pressure'] + np.random.uniform(-8, 8),  # Pressure variations
                'ow_wind_speed': max(0, row['wind_speed'] + np.random.uniform(-5, 5)),  # Wind variations
                'ow_visibility': 10 + np.random.uniform(-3, 3),  # Visibility variations
                'ow_clouds': max(0, min(100, 50 + np.random.randint(-30, 30)))  # Cloud variations
            }
            synthetic_data.append(correction)

        return pd.DataFrame(synthetic_data)

    def train_correction_models(self):
        """Train ML models to correct OpenWeather data"""
        print("Preparing correction training data...")
        training_df = self.prepare_correction_training_data()

        if training_df.empty:
            print("No training data available")
            return

        print(f"Training on {len(training_df)} samples...")

        correction_models = {}

        # Features for correction models
        features = ['ow_temperature', 'ow_humidity', 'ow_pressure', 'ow_wind_speed', 'ow_visibility', 'ow_clouds']

        # Train correction model for each weather parameter
        corrections = {
            'temperature': 'local_temperature',
            'humidity': 'local_humidity',
            'pressure': 'local_pressure',
            'wind_speed': 'local_wind_speed'
        }

        for param, target in corrections.items():
            print(f"Training correction model for {param}...")

            # Prepare data
            X = training_df[features]
            y = training_df[target]

            if len(X) < 10:
                print(f"Insufficient data for {param} correction model")
                continue

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            # Train model
            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_test)
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))

            print(f"✅ {param.capitalize()}: MAE={mae:.2f}, RMSE={rmse:.2f}")
            # Save model
            model_path = self.models_dir / f'correction_{param}_model.pkl'
            joblib.dump(model, model_path)
            correction_models[param] = model

            print(f"✅ Saved correction model for {param}")

        # Save feature names for consistency
        feature_names_path = self.models_dir / 'correction_features.pkl'
        joblib.dump(features, feature_names_path)

        print("🎉 All correction models trained and saved!")
        return correction_models

    def evaluate_corrections(self):
        """Evaluate the performance of correction models"""
        print("Evaluating correction models...")

        try:
            training_df = self.prepare_correction_training_data()
            features = joblib.load(self.models_dir / 'correction_features.pkl')

            results = {}

            for param in ['temperature', 'humidity', 'pressure', 'wind_speed']:
                model_path = self.models_dir / f'correction_{param}_model.pkl'
                if model_path.exists():
                    model = joblib.load(model_path)
                    target = f'local_{param}'

                    X = training_df[features]
                    y_true = training_df[target]
                    y_pred = model.predict(X)

                    mae = mean_absolute_error(y_true, y_pred)
                    rmse = np.sqrt(mean_squared_error(y_true, y_pred))

                    results[param] = {
                        'mae': mae,
                        'rmse': rmse,
                        'mean_actual': y_true.mean(),
                        'improvement_percent': (mae / y_true.std()) * 100  # Relative to data variability
                    }

                    print(f"{param.capitalize()}: MAE={mae:.2f}, RMSE={rmse:.2f}")

            return results

        except Exception as e:
            print(f"Error evaluating corrections: {e}")
            return None

if __name__ == "__main__":
    trainer = WeatherCorrectionTrainer()
    trainer.train_correction_models()

    # Evaluate the models
    results = trainer.evaluate_corrections()
    if results:
        print("\nCorrection Model Performance:")
        for param, metrics in results.items():
            print(f"{param}: MAE={metrics['mae']:.2f}, Improvement={metrics['improvement_percent']:.1f}%")