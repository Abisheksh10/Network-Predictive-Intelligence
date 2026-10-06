import React from 'react';

export default function StatusBanner({ error, onRetry }) {
  if (!error) return null;

  return (
    <div className="status-banner error-banner">
      <div className="banner-content">
        <span className="banner-icon">⚠️</span>
        <span className="banner-text">
          <strong>API Unavailable:</strong> {error}
        </span>
      </div>
      {onRetry && (
        <button className="banner-retry-btn" onClick={onRetry}>
          Retry Connection
        </button>
      )}
    </div>
  );
}