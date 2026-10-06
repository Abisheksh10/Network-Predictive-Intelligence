import React, { useState, useEffect, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, GeoJSON } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { fetchHotspots, fetchNetworkAlerts } from '../api';
import StatusBanner from '../components/StatusBanner';

export default function HotspotsMap({ onSelectGrid }) {
  const [geoData, setGeoData] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [limitFilter, setLimitFilter] = useState(50);
  const [selectedGridId, setSelectedGridId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const geojsonLayerRef = useRef(null);

  // 1. Fetch GeoJSON
  useEffect(() => {
    let isMounted = true;
    fetch('/reference/milano-grid.geojson')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load static milano-grid.geojson');
        return res.json();
      })
      .then((data) => {
        if (isMounted) setGeoData(data);
      })
      .catch((err) => {
        if (isMounted) setError(`GeoJSON Load Error: ${err.message}`);
      });
    return () => { isMounted = false; };
  }, []);

  // 2. Fetch Data
  const loadApiData = async () => {
    setLoading(true);
    setError(null);
    try {
      const activeSeverity = severityFilter === 'ALL' ? null : severityFilter;
      const [hotspotRes, alertRes] = await Promise.all([
        fetchHotspots(limitFilter),
        fetchNetworkAlerts(limitFilter, activeSeverity)
      ]);
      setHotspots(hotspotRes.hotspots || []);
      setAlerts(alertRes.alerts || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadApiData();
  }, [limitFilter, severityFilter]);

  // 3. Grid Lookup Map: Maps numeric grid_id to severity & activity
  const gridStatusMap = useMemo(() => {
    const map = new Map();
    const rankPriority = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };

    // When viewing alerts, map all filtered alerts
    alerts.forEach((a) => {
      const gid = Number(a.grid_id);
      const existing = map.get(gid);
      const currentRank = rankPriority[a.severity] || 1;
      const existingRank = existing ? (rankPriority[existing.severity] || 0) : 0;

      if (currentRank >= existingRank) {
        map.set(gid, {
          grid_id: gid,
          severity: a.severity,
          activity: Math.max(existing?.activity || 0, a.activity_measure || 0),
          reason: a.reason,
          risk_level: a.risk_level
        });
      }
    });

    // When viewing ALL, merge hotspots
    if (severityFilter === 'ALL') {
      hotspots.forEach((h) => {
        const gid = Number(h.grid_id);
        if (!map.has(gid)) {
          let sev = 'LOW';
          if (h.total_activity >= 12000) sev = 'CRITICAL';
          else if (h.total_activity >= 6000) sev = 'HIGH';
          else if (h.total_activity >= 2500) sev = 'MEDIUM';

          map.set(gid, {
            grid_id: gid,
            severity: sev,
            activity: h.total_activity,
            reason: `Hotspot Rank #${h.rank}`,
            risk_level: h.risk_level
          });
        }
      });
    }

    return map;
  }, [hotspots, alerts, severityFilter]);

  // 4. Multi-color polygon styling
  const styleFeature = (feature) => {
    const rawId = feature.properties?.cellId ?? feature.properties?.grid_id ?? feature.id;
    const cellId = Number(rawId);
    const info = gridStatusMap.get(cellId);
    const isSelected = selectedGridId === cellId;

    if (isSelected) {
      return {
        color: '#ffffff',
        weight: 3,
        fillColor: '#38bdf8',
        fillOpacity: 0.95
      };
    }

    if (!info) {
      return {
        color: '#334155',
        weight: 0.5,
        fillColor: '#1e293b',
        fillOpacity: 0.06
      };
    }

    // Color by severity
    if (info.severity === 'CRITICAL') {
      return { color: '#ef4444', weight: 2, fillColor: '#ef4444', fillOpacity: 0.85 }; // Red
    }
    if (info.severity === 'HIGH') {
      return { color: '#f97316', weight: 1.8, fillColor: '#f97316', fillOpacity: 0.75 }; // Orange
    }
    if (info.severity === 'MEDIUM') {
      return { color: '#eab308', weight: 1.5, fillColor: '#eab308', fillOpacity: 0.65 }; // Yellow
    }
    // LOW
    return { color: '#3b82f6', weight: 1.2, fillColor: '#3b82f6', fillOpacity: 0.55 }; // Blue
  };

  // 5. Tooltip & Click Handler
  const onEachFeature = (feature, layer) => {
    const rawId = feature.properties?.cellId ?? feature.properties?.grid_id ?? feature.id;
    const cellId = Number(rawId);
    const info = gridStatusMap.get(cellId);

    const tooltipContent = info
      ? `<strong>Grid ${cellId} [${info.severity}]</strong><br/>Activity: ${info.activity?.toLocaleString() || 'N/A'}`
      : `Grid ${cellId} [NORMAL]`;

    layer.bindTooltip(tooltipContent, { sticky: true });

    layer.on({
      click: () => {
        setSelectedGridId(cellId);
        if (onSelectGrid) onSelectGrid(cellId);
      },
      mouseover: (e) => {
        e.target.setStyle({ weight: 3, color: '#ffffff' });
      },
      mouseout: (e) => {
        if (geojsonLayerRef.current) {
          geojsonLayerRef.current.resetStyle(e.target);
        }
      }
    });
  };

  const isSeverityActive = severityFilter !== 'ALL';
  const tableData = isSeverityActive ? alerts : hotspots;

  return (
    <div className="overview-page">
      <div className="page-header">
        <h2>Hotspots, Operational Alerts & Milan Map</h2>
        <div className="controls-row">
          <label>
            Limit:
            <select
              className="select-control"
              value={limitFilter}
              onChange={(e) => setLimitFilter(Number(e.target.value))}
            >
              <option value={20}>Top 20</option>
              <option value={50}>Top 50</option>
              <option value={100}>Top 100</option>
            </select>
          </label>

          <label>
            Alert Severity:
            <select
              className="select-control"
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical (≥ 12,000)</option>
              <option value="HIGH">High (6,000 – 12,000)</option>
              <option value="MEDIUM">Medium (2,500 – 6,000)</option>
              <option value="LOW">Low (1,000 – 2,500)</option>
            </select>
          </label>
        </div>
      </div>

      <StatusBanner error={error} onRetry={loadApiData} />

      {/* Legend */}
      <div className="map-legend">
        <span className="legend-item"><span className="legend-badge" style={{ background: '#ef4444', color: '#fff' }}>CRITICAL</span> Extreme (≥12k)</span>
        <span className="legend-item"><span className="legend-badge" style={{ background: '#f97316', color: '#fff' }}>HIGH</span> Surge (6k–12k)</span>
        <span className="legend-item"><span className="legend-badge" style={{ background: '#eab308', color: '#000' }}>MEDIUM</span> Moderate (2.5k–6k)</span>
        <span className="legend-item"><span className="legend-badge" style={{ background: '#3b82f6', color: '#fff' }}>LOW</span> Baseline (1k–2.5k)</span>
      </div>

      <div className="map-and-table-grid">
        {/* Map */}
        <div className="map-wrapper">
          {geoData ? (
            <MapContainer
              center={[45.4642, 9.1900]}
              zoom={12}
              preferCanvas={true}
              style={{ width: '100%', height: '540px', borderRadius: '8px' }}
            >
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; OpenStreetMap contributors'
              />
              <GeoJSON
                ref={geojsonLayerRef}
                key={`geojson-${limitFilter}-${severityFilter}-${alerts.length}-${selectedGridId}`}
                data={geoData}
                style={styleFeature}
                onEachFeature={onEachFeature}
              />
            </MapContainer>
          ) : (
            <div className="state-container">
              <div className="loading-spinner"></div>
              <p>Loading Geographic Grid Reference...</p>
            </div>
          )}
        </div>

        {/* Table */}
        <div className="table-wrapper">
          <h3>
            {isSeverityActive 
              ? `${severityFilter} Alerts (${alerts.length})`
              : `Top ${hotspots.length} Volume Hotspots`}
          </h3>
          <div className="table-scroll">
            <table className="noc-table">
              <thead>
                <tr>
                  <th>{isSeverityActive ? 'Severity' : 'Rank'}</th>
                  <th>Grid ID</th>
                  <th>Total Activity</th>
                  <th>{isSeverityActive ? 'Reason' : 'Action'}</th>
                </tr>
              </thead>
              <tbody>
                {tableData.map((item, idx) => {
                  const gid = item.grid_id;
                  const isSelected = selectedGridId === gid;
                  const sev = item.severity || 'LOW';

                  return (
                    <tr
                      key={`${gid}-${idx}`}
                      className={isSelected ? 'selected-row' : ''}
                      onClick={() => setSelectedGridId(gid)}
                    >
                      <td>
                        {isSeverityActive ? (
                          <span className={`status-tag tag-${sev.toLowerCase()}`}>
                            {sev}
                          </span>
                        ) : (
                          `#${item.rank}`
                        )}
                      </td>
                      <td><strong>Grid {gid}</strong></td>
                      <td>
                        {(item.total_activity ?? item.activity_measure)?.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                      </td>
                      <td>
                        {isSeverityActive ? (
                          <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{item.reason}</span>
                        ) : (
                          <button
                            className="drilldown-btn"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (onSelectGrid) onSelectGrid(gid);
                            }}
                          >
                            Explore ➔
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}