import pandas as pd
from pathlib import Path

P = Path(__file__).resolve().parent.parent / 'data' / 'philippines_weather_featured_v2.csv'
df = pd.read_csv(P, nrows=1)
print('COLUMNS:', df.columns.tolist())
