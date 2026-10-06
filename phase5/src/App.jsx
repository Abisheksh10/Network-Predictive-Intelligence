import React, { useState } from 'react';
import NetworkOverview from './pages/NetworkOverview';
import GridExplorer from './pages/GridExplorer';
import HotspotsMap from './pages/HotspotsMap';
import PredictiveRisk from './pages/PredictiveRisk';
import './App.css';

export default function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedGridForExplorer, setSelectedGridForExplorer] = useState(null);

  const handleOpenGridInExplorer = (gridId) => {
    setSelectedGridForExplorer(gridId);
    setActiveTab('drilldown');
  };

  return (
    <div className="noc-container">
      {/* Navigation Bar */}
      <header className="navbar">
        <div className="nav-brand">
          <span>📡</span>
          <span>NOC Intelligence Platform</span>
        </div>
        <nav className="nav-links">
          <button 
            className={`nav-btn ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Network Overview
          </button>
          <button 
            className={`nav-btn ${activeTab === 'hotspots' ? 'active' : ''}`}
            onClick={() => setActiveTab('hotspots')}
          >
            Hotspots & Alerts
          </button>
          <button 
            className={`nav-btn ${activeTab === 'drilldown' ? 'active' : ''}`}
            onClick={() => setActiveTab('drilldown')}
          >
            Grid Drill-Down
          </button>
          <button 
            className={`nav-btn ${activeTab === 'predict' ? 'active' : ''}`}
            onClick={() => setActiveTab('predict')}
          >
            Predictive Risk
          </button>
        </nav>
      </header>

      {/* Main Page View */}
      <main>
        {activeTab === 'overview' && <NetworkOverview />}

        {activeTab === 'hotspots' && (
          <HotspotsMap onSelectGrid={handleOpenGridInExplorer} />
        )}

        {activeTab === 'drilldown' && (
          <GridExplorer initialGridId={selectedGridForExplorer} />
        )}

        {activeTab === 'predict' && (
          <PredictiveRisk defaultGridId={selectedGridForExplorer || 5161} />
        )}
      </main>
    </div>
  );
}