/**
 * NOC API Client Layer
 * Location: D:\project1\phase5\src\api.js
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export async function fetchNetworkSummary(filters = {}) {
  // Supports either fetchNetworkSummary("2013-11-07T23:00:00") or fetchNetworkSummary({ asOf, startTime, endTime, date, hour })
  const params = new URLSearchParams();

  if (typeof filters === 'string') {
    params.append('as_of', filters);
  } else if (filters && typeof filters === 'object') {
    if (filters.asOf) params.append('as_of', filters.asOf);
    if (filters.startTime) params.append('start_time', filters.startTime);
    if (filters.endTime) params.append('end_time', filters.endTime);
    if (filters.date) params.append('date', filters.date);
    if (filters.hour !== undefined && filters.hour !== '' && filters.hour !== null) {
      params.append('hour', filters.hour);
    }
  }

  const queryString = params.toString();
  const url = queryString ? `${API_BASE_URL}/network/summary?${queryString}` : `${API_BASE_URL}/network/summary`;

  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
  return await response.json();
}

export async function fetchGridActivity(gridId, asOf = null) {
  const url = asOf 
    ? `${API_BASE_URL}/network/grid/${gridId}?as_of=${encodeURIComponent(asOf)}`
    : `${API_BASE_URL}/network/grid/${gridId}`;

  const response = await fetch(url);
  if (!response.ok) {
    const errDetail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errDetail.detail || `HTTP Error ${response.status}`);
  }
  return await response.json();
}

export async function fetchHotspots(limit = 20, asOf = null) {
  const url = asOf 
    ? `${API_BASE_URL}/network/hotspots?limit=${limit}&as_of=${encodeURIComponent(asOf)}`
    : `${API_BASE_URL}/network/hotspots?limit=${limit}`;

  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
  return await response.json();
}

export async function fetchNetworkAlerts(limit = 50, severity = null, asOf = null) {
  let url = `${API_BASE_URL}/network/alerts?limit=${limit}`;
  if (severity) url += `&severity=${severity}`;
  if (asOf) url += `&as_of=${encodeURIComponent(asOf)}`;

  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP Error ${response.status}`);
  return await response.json();
}

export async function fetchGridFeatures(gridId, asOf = null) {
  const url = asOf 
    ? `${API_BASE_URL}/network/grid/${gridId}/features?as_of=${encodeURIComponent(asOf)}`
    : `${API_BASE_URL}/network/grid/${gridId}/features`;

  const response = await fetch(url);
  if (!response.ok) {
    const errDetail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errDetail.detail || `HTTP Error ${response.status}`);
  }
  return await response.json();
}

export async function predictNetworkRisk(payload) {
  const response = await fetch(`${API_BASE_URL}/network/predict-risk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const errDetail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errDetail.detail || `HTTP Error ${response.status}`);
  }
  return await response.json();
}


export async function investigateGridRisk(gridId) {
  const response = await fetch(`${API_BASE_URL}/network/investigate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ grid_id: Number(gridId) })
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `Agent investigation failed with HTTP ${response.status}`);
  }

  return response.json();
}


export async function explainRiskWithClaude(payload) {
  const response = await fetch(`${API_BASE_URL}/network/explain-risk`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP Error ${response.status}`);
  }

  return response.json();
}