import React, { useState, useEffect } from 'react';
import { fetchGridActivity } from '../api';
import StatusBanner from '../components/StatusBanner';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

export default function GridExplorer({ initialGridId }) {
  const [searchInput, setSearchInput] = useState(initialGridId ? String(initialGridId) : '');
  const [gridData, setGridData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const executeSearch = async (gridId) => {
    if (!gridId || isNaN(gridId)) return;
    setLoading(true);
    setError(null);
    setGridData(null);
    try {
      const data = await fetchGridActivity(gridId);
      setGridData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialGridId) {
      setSearchInput(String(initialGridId));
      executeSearch(initialGridId);
    }
  }, [initialGridId]);

  const handleSearch = (e) => {
    e.preventDefault();
    executeSearch(searchInput);
  };

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{ backgroundColor: '#1e293b', border: '1px solid #334155', padding: '10px', borderRadius: '6px' }}>
          <p style={{ margin: '0 0 8px 0', color: '#f8fafc', fontWeight: 'bold' }}>{label}</p>
          {payload.map((entry, index) => (
            <div key={index} style={{ color: entry.color, fontSize: '0.9rem', margin: '4px 0' }}>
              {entry.name}: {entry.value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="overview-page">
      <div className="page-header">
        <h2>Grid Activity Explorer</h2>
      </div>

      <form className="search-form" onSubmit={handleSearch}>
        <input 
          type="number" 
          className="search-input"
          placeholder="Enter Milan Grid ID (1 - 10000)..." 
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          min="1"
          max="10000"
        />
        <button type="submit" className="nav-btn active" disabled={loading}>
          {loading ? 'Searching...' : 'Explore Grid'}
        </button>
      </form>

      <div style={{ marginTop: '20px' }}>
        <StatusBanner error={error} />
      </div>

      {!loading && !error && gridData && (
        <div className="chart-container" style={{ marginTop: '24px' }}>
          <div className="as-of-container" style={{ display: 'inline-flex', marginBottom: '20px' }}>
            <span className="as-of-label">Grid {gridData.grid_id} Center:</span>
            <span className="as-of-value">
              {gridData.centroid_lon.toFixed(4)} E, {gridData.centroid_lat.toFixed(4)} N
            </span>
            <span className="as-of-label" style={{ marginLeft: '12px' }}>Points:</span>
            <span className="as-of-value">{gridData.data_points_count} hours</span>
          </div>

          <div style={{ backgroundColor: 'var(--bg-card)', padding: '20px', borderRadius: '10px', border: '1px solid var(--border)' }}>
            <h3 style={{ marginTop: 0, marginBottom: '20px', color: 'var(--text-main)' }}>
              Trailing 24-Hour Activity
            </h3>
            
            <div style={{ width: '100%', height: 400 }}>
              <ResponsiveContainer>
                <LineChart data={gridData.series} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                  <XAxis 
                    dataKey="timestamp" 
                    stroke="#94a3b8" 
                    tickFormatter={(tick) => {
                      const d = new Date(tick);
                      return `${String(d.getUTCHours()).padStart(2, '0')}:00`;
                    }}
                  />
                  <YAxis yAxisId="left" stroke="#94a3b8" tickFormatter={(v) => (v / 1000).toFixed(1) + 'k'} />
                  <YAxis yAxisId="right" orientation="right" stroke="#94a3b8" />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  <Line yAxisId="left" type="monotone" dataKey="total_activity" name="Total Activity" stroke="#38bdf8" strokeWidth={3} dot={false} />
                  <Line yAxisId="left" type="monotone" dataKey="internet_activity" name="Internet" stroke="#818cf8" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                  <Line yAxisId="right" type="monotone" dataKey="total_calls" name="Voice Calls" stroke="#22c55e" strokeWidth={2} dot={false} />
                  <Line yAxisId="right" type="monotone" dataKey="total_sms" name="SMS" stroke="#fbbf24" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}