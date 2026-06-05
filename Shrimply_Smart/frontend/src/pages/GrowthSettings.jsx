import React, { useState, useEffect } from 'react';
import authService from '../services/auth';
import { EFFECTIVE_API_BASE } from '../services/apiConfig';

export default function GrowthSettings() {
  const [seasons, setSeasons] = useState([]);
  const [selectedSeasonId, setSelectedSeasonId] = useState(null);
  const [formData, setFormData] = useState({
    current_shrimp_quantity: '',
    average_shrimp_weight_grams: '',
    stocking_density: '',
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  useEffect(() => {
    const fetchSeasons = async () => {
      try {
        setLoading(true);
        const res = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/`);
        const seasonsJson = await res.json();
        const seasonsList = seasonsJson?.results || seasonsJson || [];
        setSeasons(seasonsList);

        // Auto-select active season
        const activeSeason = seasonsList.find(s => s.is_active);
        if (activeSeason) {
          setSelectedSeasonId(activeSeason.id);
          loadSeasonData(activeSeason.id);
        } else if (seasonsList.length > 0) {
          setSelectedSeasonId(seasonsList[0].id);
          loadSeasonData(seasonsList[0].id);
        }
      } catch (err) {
        console.error('Error fetching seasons:', err);
        setMessage({ type: 'error', text: 'Failed to load seasons' });
      } finally {
        setLoading(false);
      }
    };

    fetchSeasons();
  }, []);

  const loadSeasonData = async (seasonId) => {
    try {
      const res = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/`);
      const season = await res.json();
      setFormData({
        current_shrimp_quantity: season.current_shrimp_quantity || '',
        average_shrimp_weight_grams: season.average_shrimp_weight_grams || '',
        stocking_density: season.stocking_density || '',
      });
    } catch (err) {
      console.error('Error loading season data:', err);
    }
  };

  const handleSeasonChange = (e) => {
    const seasonId = parseInt(e.target.value);
    setSelectedSeasonId(seasonId);
    loadSeasonData(seasonId);
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedSeasonId) {
      setMessage({ type: 'error', text: 'Please select a season' });
      return;
    }

    setSaving(true);
    try {
      const payload = {
        current_shrimp_quantity: formData.current_shrimp_quantity ? parseInt(formData.current_shrimp_quantity) : undefined,
        average_shrimp_weight_grams: formData.average_shrimp_weight_grams ? parseFloat(formData.average_shrimp_weight_grams) : undefined,
      };

      // Remove undefined values
      Object.keys(payload).forEach(key => payload[key] === undefined && delete payload[key]);

      const res = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${selectedSeasonId}/update_shrimp_quantity/`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Failed to update');
      setMessage({ type: 'success', text: '✅ Settings updated successfully!' });
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      console.error('Error updating settings:', err);
      setMessage({ type: 'error', text: err?.message || 'Failed to update settings' });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
        <div className="flex items-center justify-center">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
        </div>
      </div>
    );
  }

  if (seasons.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
        <div className="max-w-2xl mx-auto bg-white p-8 rounded-lg shadow">
          <p className="text-center text-slate-600">No seasons found. Create a season in History Overview first.</p>
        </div>
      </div>
    );
  }

  const selectedSeason = seasons.find(s => s.id === selectedSeasonId);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 p-6">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-slate-900">⚙️ Growth Settings</h1>
          <p className="text-slate-600 mt-2">Configure shrimp pond parameters and population tracking</p>
        </div>

        {/* Messages */}
        {message && (
          <div className={`mb-6 p-4 rounded-lg ${
            message.type === 'success'
              ? 'bg-green-100 text-green-800 border border-green-300'
              : 'bg-red-100 text-red-800 border border-red-300'
          }`}>
            {message.text}
          </div>
        )}

        {/* Season Card */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4 text-slate-900">Select Season</h2>
          <select
            value={selectedSeasonId}
            onChange={handleSeasonChange}
            className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {seasons.map(season => (
              <option key={season.id} value={season.id}>
                {season.name} {season.is_active ? '🟢 Active' : ''}
              </option>
            ))}
          </select>

          {selectedSeason && (
            <div className="mt-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-slate-600"><strong>Started:</strong> {new Date(selectedSeason.start_date).toLocaleDateString()}</p>
              {selectedSeason.days_active && (
                <p className="text-sm text-slate-600 mt-1"><strong>Days Active:</strong> {selectedSeason.days_active}</p>
              )}
            </div>
          )}
        </div>

        {/* Settings Form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-6 text-slate-900">Pond Population</h2>

          <div className="space-y-6">
            {/* Shrimp Quantity */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                🦐 Current Shrimp Quantity
              </label>
              <input
                type="number"
                name="current_shrimp_quantity"
                value={formData.current_shrimp_quantity}
                onChange={handleInputChange}
                placeholder="e.g., 50000"
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-slate-500 mt-1">Total number of shrimp currently in the pond</p>
            </div>

            {/* Average Weight */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                ⚖️ Average Shrimp Weight (grams)
              </label>
              <input
                type="number"
                step="0.01"
                name="average_shrimp_weight_grams"
                value={formData.average_shrimp_weight_grams}
                onChange={handleInputChange}
                placeholder="e.g., 5.5"
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <p className="text-xs text-slate-500 mt-1">Average weight per shrimp (sample at least 20 shrimp)</p>
            </div>

            {/* Stocking Density - Read Only Info */}
            {formData.stocking_density && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  📊 Stocking Density
                </label>
                <input
                  type="number"
                  value={formData.stocking_density}
                  disabled
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg bg-slate-100 text-slate-600"
                />
                <p className="text-xs text-slate-500 mt-1">Initial stocking density (read-only)</p>
              </div>
            )}

            {/* Calculated Stats */}
            {formData.current_shrimp_quantity && formData.average_shrimp_weight_grams && (
              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-200">
                <div className="bg-blue-50 p-4 rounded-lg">
                  <p className="text-xs text-slate-600">Total Biomass</p>
                  <p className="text-xl font-bold text-blue-600">
                    {(parseInt(formData.current_shrimp_quantity) * parseFloat(formData.average_shrimp_weight_grams) / 1000).toFixed(1)}
                    <span className="text-sm ml-1">kg</span>
                  </p>
                </div>
                {selectedSeason?.entry_count && (
                  <div className="bg-green-50 p-4 rounded-lg">
                    <p className="text-xs text-slate-600">Survival Rate</p>
                    <p className="text-xl font-bold text-green-600">
                      {((parseInt(formData.current_shrimp_quantity) / selectedSeason.entry_count) * 100).toFixed(1)}
                      <span className="text-sm ml-1">%</span>
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Submit Button */}
          <div className="mt-8 flex gap-4">
            <button
              type="submit"
              disabled={saving}
              className="flex-1 px-6 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:bg-slate-400 transition"
            >
              {saving ? '💾 Saving...' : '💾 Save Settings'}
            </button>
            <button
              type="button"
              onClick={() => selectedSeasonId && loadSeasonData(selectedSeasonId)}
              className="px-6 py-3 bg-slate-200 text-slate-700 font-semibold rounded-lg hover:bg-slate-300 transition"
            >
              Reset
            </button>
          </div>
        </form>

        {/* Help Section */}
        <div className="mt-6 bg-amber-50 border border-amber-200 rounded-lg p-6">
          <h3 className="font-semibold text-amber-900 mb-3">💡 Tips</h3>
          <ul className="text-sm text-amber-800 space-y-2">
            <li>✓ Update shrimp quantity after observing any mortality</li>
            <li>✓ Weigh at least 20 shrimp and calculate average for accuracy</li>
            <li>✓ Update daily or every 2-3 days for best predictions</li>
            <li>✓ Changes are automatically used in growth predictions</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
