"""
Run a small inference validation across multiple cities to ensure the
WeatherPredictor uses per-location LSTMs when available and falls back gracefully.
"""
from backend.api.weather_predictor import weather_predictor

CITIES = [
    'Calapan',
    'Bacolod',
    'Oriental Mindoro',
    'Pinamalayan',
    'San Carlos',
    'Manila',
]

if __name__ == '__main__':
    for city in CITIES:
        print('---')
        print('City:', city)
        try:
            pred = weather_predictor.predict_tomorrow(city=city, save_to_db=False)
            print('Prediction:', pred)
        except Exception as e:
            print('Error running prediction for', city, e)
