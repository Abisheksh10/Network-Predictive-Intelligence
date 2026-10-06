import React, { useState, useEffect } from 'react';
import { fetchNetworkSummary } from '../api';
import MetricCard from '../components/MetricCard';
import StatusBanner from '../components/StatusBanner';

export default function NetworkOverview() {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter States
  const [filterMode, setFilterMode] = useState('as_of'); // 'as_of' | 'range' | 'date_hour'
  const [asOfInput, setAsOfInput] = useState('');
  const [startTimeInput, setStartTimeInput] = useState('');
  const [endTimeInput, setEndTimeInput] = useState('');
  const [dateInput, setDateInput] = useState('');
  const [hourInput, setHourInput] = useState('');

  const loadData = async (activeFilters = {}) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchNetworkSummary(activeFilters);
      setSummary(data);
      // Pre-fill default datetime input from API response if empty
      if (!asOfInput && data.as_of) {
        setAsOfInput(data.as_of.substring(0, 16));
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApplyFilter = (e) => {
    e.preventDefault();
    const queryPayload = {};

    if (filterMode === 'as_of' && asOfInput) {
      queryPayload.asOf = asOfInput.length === 16 ? `${asOfInput}:00` : asOfInput;
    } else if (filterMode === 'range') {
      if (startTimeInput) queryPayload.startTime = startTimeInput.length === 16 ? `${startTimeInput}:00` : startTimeInput;
      if (endTimeInput) queryPayload.endTime = endTimeInput.length === 16 ? `${endTimeInput}:00` : endTimeInput;
    } else if (filterMode === 'date_hour') {
      if (dateInput) queryPayload.date = dateInput;
      if (hourInput !== '') queryPayload.hour = parseInt(hourInput, 10);
    }

    loadData(queryPayload);
  };

  const handleReset = () => {
    setAsOfInput('');
    setStartTimeInput('');
    setEndTimeInput('');
    setDateInput('');
    setHourInput('');
    loadData({});
  };

  return (
    <div className="overview-page">
      <div className="page-header">
        <h2>Network Operational Overview</h2>
        {summary && (
          <div className="as-of-container">
            <span className="as-of-label">Reporting Window:</span>
            <span className="as-of-value">
              {summary.window_start ? `${summary.window_start.replace('T', ' ')} to ` : 'Cumulative to '}
              {summary.as_of.replace('T', ' ')} UTC
            </span>
          </div>
        )}
      </div>

      {/* Date/Time Filter Toolbar */}
      <div className="filter-toolbar card" style={{ padding: '1rem', marginBottom: '1.5rem', background: '#1e293b', borderRadius: '8px' }}>
        <form onSubmit={handleApplyFilter} style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
              Filter By
            </label>
            <select
              value={filterMode}
              onChange={(e) => setFilterMode(e.target.value)}
              style={{ padding: '0.5rem', borderRadius: '4px', background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
            >
              <option value="as_of">Effective Cutoff (as_of)</option>
              <option value="range">Datetime Interval (Range)</option>
              <option value="date_hour">Specific Date & Hour</option>
            </select>
          </div>

          {filterMode === 'as_of' && (
            <div>
              <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                Cutoff Datetime
              </label>
              <input
                type="datetime-local"
                value={asOfInput}
                onChange={(e) => setAsOfInput(e.target.value)}
                style={{ padding: '0.5rem', borderRadius: '4px', background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
              />
            </div>
          )}

          {filterMode === 'range' && (
            <>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                  Start Datetime
                </label>
                <input
                  type="datetime-local"
                  value={startTimeInput}
                  onChange={(e) => setStartTimeInput(e.target.value)}
                  style={{ padding: '0.5rem', borderRadius: '4px', background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                  End Datetime
                </label>
                <input
                  type="datetime-local"
                  value={endTimeInput}
                  onChange={(e) => setEndTimeInput(e.target.value)}
                  style={{ padding: '0.5rem', borderRadius: '4px', background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
                />
              </div>
            </>
          )}

          {filterMode === 'date_hour' && (
            <>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                  Date
                </label>
                <input
                  type="date"
                  value={dateInput}
                  onChange={(e) => setDateInput(e.target.value)}
                  style={{ padding: '0.5rem', borderRadius: '4px', background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
                  Hour (0-23)
                </label>
                <input
                  type="number"
                  min="0"
                  max="23"
                  placeholder="e.g. 17"
                  value={hourInput}
                  onChange={(e) => setHourInput(e.target.value)}
                  style={{ padding: '0.5rem', width: '90px', borderRadius: '4px', background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
                />
              </div>
            </>
          )}

          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <button
              type="submit"
              style={{ padding: '0.55rem 1.2rem', borderRadius: '4px', background: '#2563eb', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}
            >
              Apply Filter
            </button>
            <button
              type="button"
              onClick={handleReset}
              style={{ padding: '0.55rem 1rem', borderRadius: '4px', background: '#475569', color: '#fff', border: 'none', cursor: 'pointer' }}
            >
              Reset to Latest
            </button>
          </div>
        </form>
      </div>

      {/* API Status Banner */}
      <StatusBanner error={error} onRetry={() => loadData({})} />

      {/* Loading State */}
      {loading && (
        <div className="state-container">
          <div className="loading-spinner"></div>
          <p>Computing operational telemetry for selected window...</p>
        </div>
      )}

      {/* Metric Cards Grid */}
      {!loading && !error && summary && (
        <div className="kpi-grid">
          <MetricCard
            label="Total Network Activity"
            value={summary.total_activity.toLocaleString(undefined, {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
            subtext="Normalized activity indicator across filtered window"
            icon="📈"
          />

          <MetricCard
            label="Active Monitored Grids"
            value={summary.active_grids.toLocaleString()}
            subtext="Spatial tiles reporting telemetry (1–10000 range)"
            icon="🗺️"
          />

          <MetricCard
            label="Diurnal Peak Hour"
            value={`${String(summary.peak_hour).padStart(2, '0')}:00`}
            subtext="Hour with highest cumulative traffic in filtered window"
            icon="⏰"
          />

          <MetricCard
            label="Top Active Hotspot"
            value={`Grid ${summary.top_grid}`}
            subtext="Spatial cell with highest aggregate activity"
            icon="🔥"
          />
        </div>
      )}
    </div>
  );
}