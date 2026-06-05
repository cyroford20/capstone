import pandas as pd
from sklearn.preprocessing import MinMaxScaler, LabelEncoder

# Load raw dataset
raw_df = pd.read_csv(str(Path(__file__).resolve().parent.parent / 'data' / 'philippines_weather_raw.csv'))

# Fill missing numeric values using interpolation
numeric_cols = ['temperature', 'humidity', 'rainfall', 'wind_speed', 'pressure']
clean_df = raw_df.copy()
clean_df[numeric_cols] = clean_df[numeric_cols].interpolate(method='linear', limit_direction='both')

# Fill missing weather_condition with the most frequent value
most_freq_condition = clean_df['weather_condition'].mode()[0]
clean_df['weather_condition'] = clean_df['weather_condition'].fillna(most_freq_condition)

# Remove duplicate rows
clean_df = clean_df.drop_duplicates()

 # Feature engineering
clean_df['date'] = pd.to_datetime(clean_df['date'])
clean_df['year'] = clean_df['date'].dt.year
clean_df['month'] = clean_df['date'].dt.month
clean_df['day'] = clean_df['date'].dt.day
clean_df['season'] = clean_df['month'].apply(lambda m: 'rainy' if m in [6,7,8,9,10,11] else 'summer')
le = LabelEncoder()
clean_df['weather_condition_encoded'] = le.fit_transform(clean_df['weather_condition'])
scaler = MinMaxScaler()
clean_df[numeric_cols] = scaler.fit_transform(clean_df[numeric_cols])

# Calculate 7-day rolling averages for each numeric feature, grouped by province and municipality
for col in numeric_cols:
	avg_col = f'{col}_7day_avg'
	clean_df[avg_col] = clean_df.groupby(['province', 'municipality'])[col].transform(lambda x: x.rolling(window=7, min_periods=1).mean())

# Save cleaned dataset
clean_df.to_csv('philippines_weather_clean.csv', index=False)
print('Saved cleaned dataset to philippines_weather_clean.csv')
