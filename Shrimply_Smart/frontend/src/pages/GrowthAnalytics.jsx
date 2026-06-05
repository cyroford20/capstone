import React, { useState, useEffect } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { format, parseISO } from 'date-fns';
import authService from '../services/auth';
import { EFFECTIVE_API_BASE } from '../services/apiConfig';

export default function GrowthAnalytics({ seasonId }) {
  const [growthMetrics, setGrowthMetrics] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('metrics');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch growth metrics
        const metricsRes = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/growth_metrics/`);
        const metricsJson = await metricsRes.json();
        const metricsData = metricsJson.results || metricsJson;
        setGrowthMetrics(metricsData);
        
        // Fetch growth predictions
        const predictionsRes = await authService.apiCall(`${EFFECTIVE_API_BASE}/seasons/${seasonId}/growth_predictions/`);
        const predictionsJson = await predictionsRes.json();
        const predictionsData = predictionsJson.results || predictionsJson;
        setPredictions(predictionsData);
        
        setError(null);
      } catch (err) {
        console.error('Error fetching data:', err);
        setError('Failed to load growth analytics');
      } finally {
        setLoading(false);
      }
    };

    if (seasonId) {
      fetchData();
    }
  }, [seasonId]);

  if (loading) {
    return <div className="p-6 text-center">Loading growth analytics...</div>;
  }

  if (error) {
    return <div className="p-6 text-red-500">{error}</div>;
  }

  // Prepare chart data
  const metricsChartData = growthMetrics.map(m => ({
    date: format(parseISO(m.date), 'MMM dd'),
    weight: m.avg_weight_grams,
    count: m.shrimp_count,
    mortality: m.daily_mortality_percent,
    feed: m.feed_amount_grams,
  }));

  const predictionsChartData = predictions.slice(0, 15).map(p => ({
    date: format(parseISO(p.forecast_date), 'MMM dd'),
    predicted_weight: p.predicted_avg_weight_grams,
    confidence: p.confidence_score,
  }));

  const latestMetric = growthMetrics[growthMetrics.length - 1];
  const nearestPrediction = predictions[0];

  return (
    <div className="space-y-6 p-6 bg-gradient-to-b from-slate-50 to-slate-100 rounded-lg">
      {/* Header Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-slate-600">Current Weight</p>
          <p className="text-2xl font-bold text-blue-600">
            {typeof latestMetric?.avg_weight_grams === 'number'
              ? `${latestMetric.avg_weight_grams.toFixed(2)}g`
              : 'N/A'}
          </p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-slate-600">Shrimp Count</p>
          <p className="text-2xl font-bold text-green-600">
            {typeof latestMetric?.shrimp_count === 'number'
              ? latestMetric.shrimp_count.toLocaleString()
              : 'N/A'}
          </p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-slate-600">Daily Gain</p>
          <p className="text-2xl font-bold text-purple-600">
            {typeof latestMetric?.daily_weight_gain_grams === 'number'
              ? `${latestMetric.daily_weight_gain_grams.toFixed(2)}g`
              : 'N/A'}
          </p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow">
          <p className="text-sm text-slate-600">Harvest Ready</p>
          <p className="text-2xl font-bold text-orange-600">
            {nearestPrediction?.estimated_harvest_date 
              ? format(parseISO(nearestPrediction.estimated_harvest_date), 'MMM dd')
              : 'N/A'
            }
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        <button
          onClick={() => setActiveTab('metrics')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'metrics'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          📊 Growth Metrics
        </button>
        <button
          onClick={() => setActiveTab('predictions')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'predictions'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          🔮 Predictions
        </button>
        <button
          onClick={() => setActiveTab('recommendations')}
          className={`px-4 py-2 font-medium ${
            activeTab === 'recommendations'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-slate-600 hover:text-slate-900'
          }`}
        >
          💡 Recommendations
        </button>
      </div>

      {/* Growth Metrics Tab */}
      {activeTab === 'metrics' && (
        <div className="space-y-4">
          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="font-semibold mb-4">Weight Progression</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={metricsChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="weight" stroke="#3b82f6" name="Avg Weight (g)" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="font-semibold mb-4">Feed & Mortality</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={metricsChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="feed" fill="#10b981" name="Feed (g)" />
                <Bar dataKey="mortality" fill="#ef4444" name="Mortality (%)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="font-semibold mb-2">Shrimp Population Trend</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={metricsChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#8b5cf6" name="Count" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Predictions Tab */}
      {activeTab === 'predictions' && (
        <div className="space-y-4">
          <div className="bg-white p-4 rounded-lg shadow">
            <h3 className="font-semibold mb-4">Growth Predictions (30 days)</h3>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={predictionsChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="predicted_weight" stroke="#f59e0b" name="Predicted Weight (g)" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {predictions.slice(0, 6).map((pred, idx) => (
              <div key={idx} className="bg-blue-50 p-3 rounded border border-blue-200">
                <p className="text-sm font-medium text-slate-700">
                  {format(parseISO(pred.forecast_date), 'MMM dd, yyyy')}
                </p>
                <p className="text-lg font-bold text-blue-600 mt-1">
                  {pred.predicted_avg_weight_grams.toFixed(2)}g
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Confidence: {pred.confidence_score}%
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations Tab */}
      {activeTab === 'recommendations' && (
        <div className="space-y-3">
          {predictions.slice(0, 5).map((pred, idx) => (
            <div key={idx} className="bg-gradient-to-r from-amber-50 to-orange-50 p-4 rounded-lg border border-orange-200">
              <p className="text-sm font-semibold text-slate-700 mb-2">
                📅 {format(parseISO(pred.forecast_date), 'MMM dd, yyyy')}
              </p>
              <p className="text-sm text-slate-600 whitespace-pre-wrap">
                {pred.recommendation}
              </p>
            </div>
          ))}

          {predictions.length === 0 && (
            <div className="text-center p-8 text-slate-500">
              No predictions available yet. Add growth metrics to generate predictions.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
