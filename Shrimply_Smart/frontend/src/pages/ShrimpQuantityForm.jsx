import React, { useState, useEffect } from 'react';
import authService from '../services/auth';
import { EFFECTIVE_API_BASE } from '../services/apiConfig';
import { format } from 'date-fns';

export default function ShrimpQuantityForm({ seasonId, onUpdate }) {
  const [formData, setFormData] = useState({
    current_shrimp_quantity: '',
    average_shrimp_weight_grams: '',
    date: format(new Date(), 'yyyy-MM-dd'),
    daily_weight_gain_grams: '',
    daily_mortality_percent: '',
    feed_amount_grams: '',
    water_temperature: '',
    water_ph: '',
    dissolved_oxygen: '',
    tds: '',
    weather_condition: 'clear',
    notes: '',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [season, setSeason] = useState(null);

  useEffect(() => {
    const fetchSeason = async () => {
      try {
        const res = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/`);
        const data = await res.json();
        setSeason(data);
        if (data.current_shrimp_quantity) {
          setFormData(prev => ({
            ...prev,
            current_shrimp_quantity: data.current_shrimp_quantity,
            average_shrimp_weight_grams: data.average_shrimp_weight_grams || '',
          }));
        }
      } catch (err) {
        console.error('Error fetching season:', err);
      }
    };

    if (seasonId) {
      fetchSeason();
    }
  }, [seasonId]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      // Update shrimp quantity on season
      if (formData.current_shrimp_quantity || formData.average_shrimp_weight_grams) {
        const updateRes = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/update_shrimp_quantity/`, {
          method: 'PATCH',
          body: JSON.stringify({
            current_shrimp_quantity: parseInt(formData.current_shrimp_quantity) || undefined,
            average_shrimp_weight_grams: parseFloat(formData.average_shrimp_weight_grams) || undefined,
          }),
        });
        if (!updateRes.ok) throw new Error('Failed to update quantity');
      }

      // Add daily growth metric
      if (formData.date) {
        const metricPayload = {
          date: formData.date,
          shrimp_count: parseInt(formData.current_shrimp_quantity) || season?.current_shrimp_quantity,
          avg_weight_grams: parseFloat(formData.average_shrimp_weight_grams) || season?.average_shrimp_weight_grams,
          daily_weight_gain_grams: parseFloat(formData.daily_weight_gain_grams) || 0,
          daily_mortality_percent: parseFloat(formData.daily_mortality_percent) || 0,
          feed_amount_grams: parseFloat(formData.feed_amount_grams) || 0,
          water_temperature: parseFloat(formData.water_temperature) || null,
          water_ph: parseFloat(formData.water_ph) || null,
          dissolved_oxygen: parseFloat(formData.dissolved_oxygen) || null,
          tds: parseFloat(formData.tds) || null,
          weather_condition: formData.weather_condition,
          notes: formData.notes,
        };

        // Remove null values
        Object.keys(metricPayload).forEach(
          key => metricPayload[key] === null && delete metricPayload[key]
        );

        const metricRes = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/add_growth_metric/`, {
          method: 'POST',
          body: JSON.stringify(metricPayload),
        });
        if (!metricRes.ok) throw new Error('Failed to add metric');
      }

      setSuccess('Data updated successfully! Growth predictions will be generated next run.');
      
      if (onUpdate) {
        onUpdate();
      }

      // Reset form but keep date
      setFormData(prev => ({
        ...prev,
        daily_weight_gain_grams: '',
        daily_mortality_percent: '',
        feed_amount_grams: '',
        water_temperature: '',
        water_ph: '',
        dissolved_oxygen: '',
        tds: '',
        weather_condition: 'clear',
        notes: '',
      }));
    } catch (err) {
      console.error('Error updating data:', err);
      setError(err?.message || 'Failed to update data');
    } finally {
      setLoading(false);
    }
  };

  const weatherOptions = ['clear', 'rainy', 'cloudy', 'hot', 'cold', 'windy'];

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <h2 className="text-xl font-bold mb-6">📊 Shrimp Quantity & Growth Metrics</h2>

      {error && (
        <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-green-100 border border-green-400 text-green-700 rounded">
          {success}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Core Quantity Data */}
        <div>
          <h3 className="font-semibold text-slate-700 mb-4">Current Pond Status</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Shrimp Quantity (count)
              </label>
              <input
                type="number"
                name="current_shrimp_quantity"
                value={formData.current_shrimp_quantity}
                onChange={handleChange}
                placeholder="e.g., 50000"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-slate-500 mt-1">Total shrimp in the pond now</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Average Weight (grams)
              </label>
              <input
                type="number"
                step="0.01"
                name="average_shrimp_weight_grams"
                value={formData.average_shrimp_weight_grams}
                onChange={handleChange}
                placeholder="e.g., 5.5"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-slate-500 mt-1">Average weight per shrimp</p>
            </div>
          </div>
        </div>

        {/* Daily Metrics */}
        <div>
          <h3 className="font-semibold text-slate-700 mb-4">Daily Metrics</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Date
              </label>
              <input
                type="date"
                name="date"
                value={formData.date}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Daily Weight Gain (g)
              </label>
              <input
                type="number"
                step="0.01"
                name="daily_weight_gain_grams"
                value={formData.daily_weight_gain_grams}
                onChange={handleChange}
                placeholder="0.25"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Daily Mortality (%)
              </label>
              <input
                type="number"
                step="0.01"
                name="daily_mortality_percent"
                value={formData.daily_mortality_percent}
                onChange={handleChange}
                placeholder="0.5"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Feed Amount (g)
              </label>
              <input
                type="number"
                step="0.1"
                name="feed_amount_grams"
                value={formData.feed_amount_grams}
                onChange={handleChange}
                placeholder="1000"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Water Temp (°C)
              </label>
              <input
                type="number"
                step="0.1"
                name="water_temperature"
                value={formData.water_temperature}
                onChange={handleChange}
                placeholder="28"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                pH Level
              </label>
              <input
                type="number"
                step="0.1"
                name="water_ph"
                value={formData.water_ph}
                onChange={handleChange}
                placeholder="7.5"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Dissolved Oxygen (mg/L)
              </label>
              <input
                type="number"
                step="0.1"
                name="dissolved_oxygen"
                value={formData.dissolved_oxygen}
                onChange={handleChange}
                placeholder="6.5"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                TDS (ppm)
              </label>
              <input
                type="number"
                step="1"
                name="tds"
                value={formData.tds}
                onChange={handleChange}
                placeholder="800"
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-600 mb-1">
                Weather
              </label>
              <select
                name="weather_condition"
                value={formData.weather_condition}
                onChange={handleChange}
                className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {weatherOptions.map(opt => (
                  <option key={opt} value={opt}>
                    {opt.charAt(0).toUpperCase() + opt.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Notes */}
        <div>
          <label className="block text-sm font-medium text-slate-600 mb-1">
            Notes (optional)
          </label>
          <textarea
            name="notes"
            value={formData.notes}
            onChange={handleChange}
            placeholder="Any observations or special conditions..."
            rows="3"
            className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Submit Button */}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={loading}
            className="px-6 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 disabled:bg-slate-400"
          >
            {loading ? '💾 Saving...' : '💾 Save Data & Update Quantity'}
          </button>
        </div>

        {season && (
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded text-sm text-slate-700">
            <p><strong>Last Updated:</strong> {season.updated_at ? format(new Date(season.updated_at), 'MMM dd, yyyy HH:mm') : 'Never'}</p>
          </div>
        )}
      </form>
    </div>
  );
}
