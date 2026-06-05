import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import authService from '../services/auth';
import { EFFECTIVE_API_BASE } from '../services/apiConfig';
import ShrimpQuantityForm from './ShrimpQuantityForm';
import GrowthAnalytics from './GrowthAnalytics';

export default function GrowthDashboard() {
  const { seasonId: paramSeasonId } = useParams();
  const [seasons, setSeasons] = useState([]);
  const [selectedSeasonId, setSelectedSeasonId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  useEffect(() => {
    const fetchSeasons = async () => {
      try {
        setLoading(true);
        const res = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/`);
        const seasonsJson = await res.json();
        const seasonsList = seasonsJson?.results || seasonsJson || [];
        setSeasons(seasonsList);

        // Set initial season
        if (paramSeasonId) {
          setSelectedSeasonId(parseInt(paramSeasonId));
        } else {
          const activeSeason = seasonsList.find(s => s.is_active);
          if (activeSeason) {
            setSelectedSeasonId(activeSeason.id);
          } else if (seasonsList.length > 0) {
            setSelectedSeasonId(seasonsList[0].id);
          }
        }
      } catch (err) {
        console.error('Error fetching seasons:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchSeasons();
  }, [paramSeasonId]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 p-6">
        <div className="text-center text-slate-300">Loading...</div>
      </div>
    );
  }

  if (seasons.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-slate-800 p-8 rounded-lg text-center">
            <p className="text-slate-400 mb-4">No seasons found. Create a new season to start tracking growth.</p>
          </div>
        </div>
      </div>
    );
  }

  const activeSeason = seasons.find(s => s.id === selectedSeasonId);

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white p-6 mb-6">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-2">🚀 Growth Prediction & Analytics Dashboard</h1>
          <p className="text-blue-100">Track shrimp growth, predict harvest dates, and optimize feeding</p>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 pb-12">
        {/* Season Selector */}
        <div className="mb-6">
          <div className="flex gap-2 flex-wrap">
            <label className="text-white font-medium mr-2 flex items-center">Select Season:</label>
            {seasons.map(season => (
              <button
                key={season.id}
                onClick={() => setSelectedSeasonId(season.id)}
                className={`px-4 py-2 rounded-lg font-medium transition-all ${
                  selectedSeasonId === season.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {season.name}
                {season.is_active && ' 🟢'}
              </button>
            ))}
          </div>
        </div>

        {/* Main Content */}
        {activeSeason && (
          <div className="space-y-6">
            {/* Season Info */}
            <div className="bg-slate-800 border border-slate-700 p-6 rounded-lg">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-slate-400 text-sm">Season Name</p>
                  <p className="text-white text-lg font-semibold">{activeSeason.name}</p>
                </div>
                <div>
                  <p className="text-slate-400 text-sm">Started</p>
                  <p className="text-white text-lg font-semibold">
                    {new Date(activeSeason.start_date).toLocaleDateString()}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400 text-sm">Days Active</p>
                  <p className="text-white text-lg font-semibold">
                    {activeSeason.days_active || 'N/A'}
                  </p>
                </div>
                <div>
                  <p className="text-slate-400 text-sm">Status</p>
                  <p className={`text-lg font-semibold ${
                    activeSeason.is_active ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {activeSeason.is_active ? '🟢 Active' : '🔴 Completed'}
                  </p>
                </div>
              </div>
            </div>

            {/* Two Column Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left: Input Form */}
              <div className="lg:col-span-1">
                <ShrimpQuantityForm
                  seasonId={selectedSeasonId}
                  onUpdate={() => setRefreshTrigger(prev => prev + 1)}
                />
              </div>

              {/* Right: Analytics */}
              <div className="lg:col-span-2">
                <GrowthAnalytics
                  seasonId={selectedSeasonId}
                  key={refreshTrigger}
                />
              </div>
            </div>

            {/* Quick Stats */}
            <div className="bg-slate-800 border border-slate-700 p-6 rounded-lg">
              <h3 className="text-white font-bold text-lg mb-4">📈 Quick Stats</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-slate-700 p-4 rounded-lg">
                  <p className="text-slate-400 text-sm">Current Count</p>
                  <p className="text-white text-2xl font-bold">
                    {activeSeason.current_shrimp_quantity?.toLocaleString() || '—'}
                  </p>
                </div>
                <div className="bg-slate-700 p-4 rounded-lg">
                  <p className="text-slate-400 text-sm">Avg Weight</p>
                  <p className="text-white text-2xl font-bold">
                    {activeSeason.average_shrimp_weight_grams?.toFixed(2) || '—'}
                    <span className="text-sm ml-1">g</span>
                  </p>
                </div>
                <div className="bg-slate-700 p-4 rounded-lg">
                  <p className="text-slate-400 text-sm">Total Biomass</p>
                  <p className="text-white text-2xl font-bold">
                    {activeSeason.current_shrimp_quantity && activeSeason.average_shrimp_weight_grams
                      ? `${(activeSeason.current_shrimp_quantity * activeSeason.average_shrimp_weight_grams / 1000).toFixed(1)}kg`
                      : '—'
                    }
                  </p>
                </div>
                <div className="bg-slate-700 p-4 rounded-lg">
                  <p className="text-slate-400 text-sm">Stocking Density</p>
                  <p className="text-white text-2xl font-bold">
                    {activeSeason.stocking_density || '—'}
                    <span className="text-sm ml-1">/m²</span>
                  </p>
                </div>
              </div>
            </div>

            {/* Information Panel */}
            <div className="bg-blue-900/30 border border-blue-700 p-6 rounded-lg">
              <h3 className="text-blue-100 font-bold text-lg mb-3">💡 How to Use</h3>
              <ul className="space-y-2 text-blue-100 text-sm">
                <li>✅ <strong>Input Data:</strong> Use the form on the left to enter daily metrics for your shrimp pond</li>
                <li>✅ <strong>Track Growth:</strong> Log shrimp count, average weight, and water quality parameters</li>
                <li>✅ <strong>Get Predictions:</strong> The ML model predicts growth trends and harvest dates</li>
                <li>✅ <strong>View Analytics:</strong> Charts show weight progression, feeding patterns, and recommendations</li>
                <li>✅ <strong>Smart Feeding:</strong> Use the feeding adjustment tool to optimize feed based on shrimp size</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
