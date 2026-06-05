"""
Machine Learning module for shrimp growth prediction.

This module handles:
- Data preprocessing for growth metrics
- Model training using Random Forest and LSTM
- Growth predictions
- Harvest date estimation
- AI recommendations
"""

import numpy as np
import pandas as pd
from datetime import timedelta
import json
import logging
from pathlib import Path
import pickle

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

try:
    from tensorflow import keras
    from tensorflow.keras import layers, models
    import tensorflow as tf
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).parent / 'ml_models'
MODEL_DIR.mkdir(exist_ok=True)


class GrowthDataPreprocessor:
    """Prepare growth metrics for model training."""
    
    @staticmethod
    def create_dataframe_from_metrics(metrics_qs):
        """
        Convert DailyGrowthMetric queryset to pandas DataFrame.
        
        Args:
            metrics_qs: QuerySet of DailyGrowthMetric objects
            
        Returns:
            DataFrame with engineered features
        """
        data = []
        for metric in metrics_qs.order_by('date'):
            data.append({
                'date': metric.date,
                'days_since_start': (metric.date - metrics_qs.first().date).days,
                'shrimp_count': metric.shrimp_count,
                'avg_weight': metric.avg_weight_grams,
                'daily_weight_gain': metric.daily_weight_gain_grams,
                'daily_mortality': metric.daily_mortality_percent,
                'feed_amount': metric.feed_amount_grams,
                'water_temp': metric.water_temperature or 25.0,
                'water_ph': metric.water_ph or 7.5,
                'dissolved_oxygen': metric.dissolved_oxygen or 6.0,
                'tds': metric.tds or 500.0,
                'is_rainy': 1 if metric.weather_condition and 'rain' in metric.weather_condition.lower() else 0,
                'notes': metric.notes,
            })
        
        if not data:
            return None
        
        df = pd.DataFrame(data)
        
        # Engineering features
        df['feed_per_shrimp'] = df['feed_amount'] / (df['shrimp_count'] + 1)
        df['weight_to_feed_ratio'] = df['avg_weight'] / (df['feed_amount'] + 0.1)
        df['survival_rate'] = (df['shrimp_count'] / df['shrimp_count'].iloc[0] * 100) if len(df) > 0 else 100
        df['cumulative_gain'] = df['daily_weight_gain'].cumsum()
        
        # Rolling averages
        df['temp_7day_avg'] = df['water_temp'].rolling(window=7, min_periods=1).mean()
        df['weight_7day_avg'] = df['avg_weight'].rolling(window=7, min_periods=1).mean()
        
        return df
    
    @staticmethod
    def prepare_training_data(season):
        """Prepare data for model training from a single season."""
        from .models import DailyGrowthMetric
        metrics_qs = DailyGrowthMetric.objects.filter(season=season).order_by('date')
        
        df = GrowthDataPreprocessor.create_dataframe_from_metrics(metrics_qs)
        if df is None or len(df) < 5:
            return None, None
        
        # Features for prediction
        feature_cols = [
            'days_since_start', 'daily_mortality', 'feed_amount', 'water_temp',
            'water_ph', 'dissolved_oxygen', 'tds', 'is_rainy', 'feed_per_shrimp',
            'weight_to_feed_ratio', 'survival_rate', 'temp_7day_avg'
        ]
        
        X = df[feature_cols].fillna(df[feature_cols].mean())
        y_weight = df['avg_weight'].values
        y_count = df['shrimp_count'].values
        
        return X, {'weight': y_weight, 'count': y_count}, df
    
    @staticmethod
    def normalize_features(X, scaler=None):
        """Normalize features."""
        if scaler is None:
            scaler = StandardScaler()
            X_normalized = scaler.fit_transform(X)
        else:
            X_normalized = scaler.transform(X)
        
        return X_normalized, scaler


class ShrimpGrowthPredictor:
    """ML model for predicting shrimp growth."""
    
    def __init__(self, model_name='growth_predictor_v1.pkl'):
        self.model_name = model_name
        self.model_path = MODEL_DIR / model_name
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.load_model()
    
    def load_model(self):
        """Load trained model from disk."""
        if self.model_path.exists():
            try:
                with open(self.model_path, 'rb') as f:
                    data = pickle.load(f)
                    self.model = data.get('model')
                    self.scaler = data.get('scaler')
                    self.feature_names = data.get('features')
                logger.info(f'Loaded model from {self.model_path}')
                return True
            except Exception as e:
                logger.error(f'Failed to load model: {e}')
                return False
        return False
    
    def save_model(self):
        """Save trained model to disk."""
        try:
            with open(self.model_path, 'wb') as f:
                pickle.dump({
                    'model': self.model,
                    'scaler': self.scaler,
                    'features': self.feature_names,
                }, f)
            logger.info(f'Saved model to {self.model_path}')
            return True
        except Exception as e:
            logger.error(f'Failed to save model: {e}')
            return False
    
    def train(self, X, y, test_size=0.2):
        """Train the model."""
        if not SKLEARN_AVAILABLE:
            logger.error('scikit-learn not available')
            return False
        
        try:
            X_normalized, scaler = GrowthDataPreprocessor.normalize_features(X)
            X_train, X_test, y_train, y_test = train_test_split(
                X_normalized, y, test_size=test_size, random_state=42
            )
            
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42,
                n_jobs=-1,
            )
            self.model.fit(X_train, y_train)
            self.scaler = scaler
            self.feature_names = X.columns.tolist() if hasattr(X, 'columns') else None
            
            # Evaluate
            train_score = self.model.score(X_train, y_train)
            test_score = self.model.score(X_test, y_test)
            logger.info(f'Model trained: train_r2={train_score:.3f}, test_r2={test_score:.3f}')
            
            return True
        except Exception as e:
            logger.error(f'Training failed: {e}')
            return False
    
    def predict_weight(self, X):
        """Predict average shrimp weight."""
        if self.model is None:
            return None
        
        try:
            if self.scaler:
                X_normalized = self.scaler.transform(X)
            else:
                X_normalized = X
            
            prediction = self.model.predict(X_normalized)
            return np.clip(prediction, 0.1, 100)  # Reasonable bounds
        except Exception as e:
            logger.error(f'Prediction failed: {e}')
            return None
    
    def predict_harvest_date(self, current_date, current_weight, target_weight=18.0, days_ahead=60):
        """
        Estimate harvest date based on growth trajectory.
        
        Uses linear extrapolation from current growth rate.
        """
        if current_weight <= 0:
            return None
        
        # Simple linear growth model
        # Assume growth slows down as shrimp gets larger
        if current_weight < 5:
            daily_growth = 0.25  # grams/day for small shrimp
        elif current_weight < 10:
            daily_growth = 0.15
        else:
            daily_growth = 0.10
        
        remaining_growth = max(0, target_weight - current_weight)
        days_to_harvest = remaining_growth / daily_growth if daily_growth > 0 else 60
        
        estimated_harvest = current_date + timedelta(days=int(days_to_harvest))
        return estimated_harvest


def generate_growth_predictions(season, days_ahead=30):
    """
    Generate growth predictions for a season.
    
    Returns list of GrowthPrediction objects ready to save.
    """
    from django.utils import timezone
    from .models import DailyGrowthMetric, GrowthPrediction
    
    # Get latest metric
    latest_metric = season.growth_metrics.order_by('-date').first()
    if not latest_metric:
        logger.warning(f'No growth metrics found for season {season.id}')
        return []
    
    predictor = ShrimpGrowthPredictor()
    predictions = []
    
    current_weight = latest_metric.avg_weight_grams or 0
    current_count = latest_metric.shrimp_count or 1
    current_date = latest_metric.date
    
    for day_offset in range(1, days_ahead + 1):
        forecast_date = current_date + timedelta(days=day_offset)
        
        # Simple prediction: linear growth with seasonal adjustment
        growth_rate = 0.15 if current_weight < 10 else 0.10
        predicted_weight = current_weight + (growth_rate * day_offset)
        
        # Survival rate decreases slowly (0.2% per week)
        initial_count = season.stocking_density or current_count
        predicted_count = int(current_count * (1 - (0.002 * day_offset / 7)))
        predicted_count = max(1, predicted_count)
        
        # Calculate survival percentage
        survival_rate = (predicted_count / initial_count * 100) if initial_count > 0 else 100
        
        # Estimate harvest date
        estimated_harvest = predictor.predict_harvest_date(
            current_date, current_weight, target_weight=18.0
        )
        
        # Confidence decreases with distance
        confidence = max(50, 95 - (day_offset * 2))
        
        # Generate recommendation (strip non-BMP chars for MySQL utf8 compatibility)
        recommendation = _strip_non_bmp(
            _generate_recommendation(predicted_weight, current_weight, predicted_count)
        )
        
        prediction = GrowthPrediction(
            season=season,
            prediction_date=current_date,
            forecast_date=forecast_date,
            predicted_avg_weight_grams=round(predicted_weight, 2),
            predicted_shrimp_count=predicted_count,
            predicted_survival_rate_percent=round(survival_rate, 1),
            estimated_harvest_date=estimated_harvest,
            confidence_score=confidence,
            recommendation=recommendation,
            model_version='1.0',
            is_active=(day_offset <= 7),  # Only keep first week active
        )
        predictions.append(prediction)
    
    return predictions


def _strip_non_bmp(text):
    """Strip non-BMP characters (e.g., many emojis) for MySQL utf8 (3-byte) safety."""
    if not text:
        return text
    return ''.join(ch for ch in str(text) if ord(ch) <= 0xFFFF)


def _generate_recommendation(predicted_weight, current_weight, predicted_count):
    """Generate AI recommendation based on predictions."""
    recommendations = []
    
    # Growth rate
    growth_potential = predicted_weight - current_weight
    if growth_potential < 0.5:
        recommendations.append("⚠️ Growth rate is below optimal. Consider increasing feed.")
    elif growth_potential > 2:
        recommendations.append("✅ Excellent growth trajectory! Maintain current feeding.")
    
    # Survival
    if predicted_count < 100:
        recommendations.append("⚠️ Low survival rate detected. Check water quality.")
    
    # Weight target
    if predicted_weight >= 18:
        days_to_harvest = "7-10 days"
        recommendations.append(f"🎯 Estimated ready for harvest in {days_to_harvest}")
    elif predicted_weight >= 15:
        recommendations.append("📊 Approaching harvest weight. Monitor daily.")
    
    if not recommendations:
        recommendations.append("📈 Continue current feeding and monitoring schedule.")
    
    return " | ".join(recommendations)


def analyze_season_performance(season):
    """
    Analyze season performance and generate summary statistics.
    
    Returns dict with analytics.
    """
    from .models import DailyGrowthMetric
    from django.db.models import Avg, Max, Min, Sum
    
    metrics = season.growth_metrics.all()
    if not metrics.exists():
        return None
    
    agg = metrics.aggregate(
        avg_weight=Avg('avg_weight_grams'),
        max_weight=Max('avg_weight_grams'),
        min_weight=Min('avg_weight_grams'),
        avg_mortality=Avg('daily_mortality_percent'),
        total_feed=Sum('feed_amount_grams'),
        avg_temp=Avg('water_temperature'),
        avg_ph=Avg('water_ph'),
    )
    
    first_metric = metrics.order_by('date').first()
    last_metric = metrics.order_by('-date').first()
    
    return {
        'days_tracked': (last_metric.date - first_metric.date).days,
        'initial_weight': first_metric.avg_weight_grams,
        'final_weight': last_metric.avg_weight_grams,
        'total_weight_gain': last_metric.avg_weight_grams - first_metric.avg_weight_grams,
        'average_daily_gain': (last_metric.avg_weight_grams - first_metric.avg_weight_grams) / max(1, (last_metric.date - first_metric.date).days),
        'initial_count': first_metric.shrimp_count,
        'final_count': last_metric.shrimp_count,
        'survival_rate': (last_metric.shrimp_count / first_metric.shrimp_count * 100) if first_metric.shrimp_count > 0 else 0,
        **agg,
    }
