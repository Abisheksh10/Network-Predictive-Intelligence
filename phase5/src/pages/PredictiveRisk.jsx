// import React, { useState, useEffect } from 'react';
// import { predictNetworkRisk, investigateGridRisk ,explainRiskWithClaude} from '../api';
// import StatusBanner from '../components/StatusBanner';

// export default function PredictiveRisk({ defaultGridId }) {
//   const [gridIdInput, setGridIdInput] = useState(defaultGridId ? String(defaultGridId) : '5161');
//   const [timestampInput, setTimestampInput] = useState('2013-11-07T15:00');

//   const [prediction, setPrediction] = useState(null);
//   const [loading, setLoading] = useState(false);
//   const [error, setError] = useState(null);

//   // Claude Agent States
//   const [aiExplainActive, setAiExplainActive] = useState(false);
//   const [aiLoading, setAiLoading] = useState(false);
//   const [aiReport, setAiReport] = useState(null);
//   const [aiError, setAiError] = useState(null);

//   // Execute binary risk evaluation (LOW vs CRITICAL)
//   const handlePredict = async (e) => {
//     if (e) e.preventDefault();

//     const idNum = parseInt(gridIdInput, 10);
//     if (isNaN(idNum) || idNum < 1 || idNum > 10000) {
//       setError('Please provide a valid Grid ID between 1 and 10000.');
//       return;
//     }

//     if (!timestampInput) {
//       setError('Please select an operational cutoff timestamp.');
//       return;
//     }

//     setLoading(true);
//     setError(null);
//     setAiExplainActive(false);
//     setAiReport(null);
//     setAiError(null);

//     try {
//       const formattedTs = timestampInput.length === 16 ? `${timestampInput}:00` : timestampInput;
//       const res = await predictNetworkRisk({
//         grid_id: idNum,
//         timestamp: formattedTs
//       });
//       setPrediction(res);
//     } catch (err) {
//       setError(err.message);
//     } finally {
//       setLoading(false);
//     }
//   };

//   // Trigger the real Claude Agent Investigation (c14_agent.py)
//   const handleRunAgentInvestigation = async () => {
//     if (!prediction) return;
//     setAiExplainActive(true);
//     setAiLoading(true);
//     setAiError(null);

//     try {
//       const payload = {
//         grid_id: prediction.grid_id,
//         timestamp: timestampInput,
//         risk_score: prediction.risk_score,
//         risk_level: prediction.risk_level,
//         features: prediction.features_used || {}
//       };
//       const res = await explainRiskWithClaude(payload);
//       setAiReport(res);
//     } catch (err) {
//       setAiError(err.message);
//     } finally {
//       setAiLoading(false);
//     }
//   };

//   useEffect(() => {
//     handlePredict();
//   }, []);

//   const getRiskBadgeClass = (level) => {
//     return level === 'CRITICAL' ? 'tag-critical' : 'tag-low';
//   };

//   return (
//     <div className="overview-page">
//       <div className="page-header">
//         <div>
//           <h2>Predictive Operational Risk View</h2>
//           <p className="sub-header-desc">
//             Point-in-time anomaly prediction: Logistic Regression classification (LOW / CRITICAL) paired with autonomous Claude agent root-cause investigation.
//           </p>
//         </div>
//       </div>

//       <StatusBanner error={error} onRetry={handlePredict} />

//       {/* Snapshot Coordinates Input Panel */}
//       <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem', background: '#1e293b', borderRadius: '8px' }}>
//         <h4 style={{ margin: '0 0 0.75rem 0', color: '#93c5fd' }}>Operational Snapshot Coordinates</h4>
//         <form onSubmit={handlePredict} style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'flex-end' }}>
//           <div>
//             <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
//               Grid ID (1–10000)
//             </label>
//             <input 
//               type="number"
//               style={{ padding: '0.55rem', borderRadius: '4px', background: '#0f172a', color: '#fff', border: '1px solid #334155', width: '130px' }}
//               value={gridIdInput}
//               onChange={(e) => setGridIdInput(e.target.value)}
//               min="1"
//               max="10000"
//               required
//             />
//           </div>

//           <div>
//             <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
//               Snapshot Cutoff (t)
//             </label>
//             <input 
//               type="datetime-local"
//               style={{ padding: '0.55rem', borderRadius: '4px', background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
//               value={timestampInput}
//               onChange={(e) => setTimestampInput(e.target.value)}
//               required
//             />
//           </div>

//           <button 
//             type="submit"
//             style={{ padding: '0.6rem 1.4rem', borderRadius: '4px', background: '#2563eb', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}
//             disabled={loading}
//           >
//             {loading ? 'Analyzing Lookback Telemetry...' : '⚡ Evaluate Risk at t+1'}
//           </button>
//         </form>
//       </div>

//       {/* Loading Indicator */}
//       {loading && !prediction && (
//         <div className="state-container" style={{ padding: '2rem', textAlign: 'center' }}>
//           <div className="loading-spinner"></div>
//           <p style={{ color: '#94a3b8', marginTop: '1rem' }}>Extracting trailing telemetry & computing risk inference...</p>
//         </div>
//       )}

//       {/* Main Results Container */}
//       <div className="prediction-output-column">
        
//         {/* REGION A: PURE ML MODEL OUTPUT */}
//         <div className="card-panel model-output-region">
//           <div className="region-tag">MACHINE LEARNING INFERENCE ARTIFACT</div>
          
//           {prediction && (
//             <div>
//               <div className="score-hero">
//                 <div>
//                   <span className="kpi-label">Operational Risk Index</span>
//                   <div className="risk-score-value">
//                     {(prediction.risk_score * 100).toFixed(1)}%
//                   </div>
//                   <span className="subtext-note">Probability of t+1 operational attention requirement</span>
//                 </div>

//                 <div className="risk-meta-block">
//                   <span className="kpi-label">Classified Level</span>
//                   <div>
//                     <span className={`status-tag ${getRiskBadgeClass(prediction.risk_level)}`}>
//                       {prediction.risk_level}
//                     </span>
//                   </div>

//                   <div style={{ marginTop: '12px' }}>
//                     <span className="kpi-label">Scoring Model Build</span>
//                     <div className="model-version-badge">
//                       <code>{prediction.model_version}</code>
//                     </div>
//                   </div>
//                 </div>
//               </div>

//               <div className="model-note-box" style={{ marginTop: '1rem' }}>
//                 <strong>Model Diagnostic:</strong> {prediction.explanation_note}
//               </div>

//               {/* Evaluated Feature Cards */}
//               {prediction.features_used && (
//                 <div style={{ marginTop: '1.25rem' }}>
//                   <h5 style={{ margin: '0 0 0.5rem 0', color: '#94a3b8' }}>
//                     Evaluated Features (Trailing Lookback Window [t-23h, t]):
//                   </h5>
//                   <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
//                     <div className="kpi-mini-card">
//                       <span className="mini-label">Avg Activity</span>
//                       <span className="mini-value">{prediction.features_used.avg_activity.toLocaleString()}</span>
//                     </div>
//                     <div className="kpi-mini-card">
//                       <span className="mini-label">Growth Rate</span>
//                       <span className="mini-value">
//                         {prediction.features_used.activity_growth > 0 
//                           ? `+${prediction.features_used.activity_growth}` 
//                           : prediction.features_used.activity_growth}
//                       </span>
//                     </div>
//                     <div className="kpi-mini-card">
//                       <span className="mini-label">Peak Ratio</span>
//                       <span className="mini-value">{prediction.features_used.peak_ratio}x</span>
//                     </div>
//                     <div className="kpi-mini-card">
//                       <span className="mini-label">Variability</span>
//                       <span className="mini-value">{prediction.features_used.variability}</span>
//                     </div>
//                     <div className="kpi-mini-card">
//                       <span className="mini-label">Active Hours</span>
//                       <span className="mini-value">{prediction.features_used.active_hours}h</span>
//                     </div>
//                     <div className="kpi-mini-card">
//                       <span className="mini-label">Data Share</span>
//                       <span className="mini-value">{(prediction.features_used.internet_share * 100).toFixed(1)}%</span>
//                     </div>
//                   </div>
//                 </div>
//               )}
//             </div>
//           )}
//         </div>

//         {/* REGION B: LIVE CLAUDE AI INVESTIGATION AGENT */}

//         <div className="card-panel narrative-explanation-region" style={{ marginTop: '1.5rem' }}>
//           <div className="region-tag ai-tag">CLAUDE AI INVESTIGATION AGENT (RCA ENGINE)</div>
          
//           <div className="ai-placeholder-content">
//             <h4>Diagnostic Narrative & Root Cause Reasoning</h4>
//             <p className="ai-desc">
//               Synthesizes evaluated feature dynamics against production logistic regression coefficients to explain <em>why</em> this risk classification was assigned.
//             </p>

//             {!aiExplainActive ? (
//               <button 
//                 className="ai-action-btn"
//                 onClick={handleRunAgentInvestigation}
//                 disabled={!prediction || loading}
//                 style={{ padding: '0.65rem 1.25rem', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600 }}
//               >
//                 ✨ Explain with AI (Claude Agent)
//               </button>
//             ) : aiLoading ? (
//               <div style={{ padding: '1.5rem', textAlign: 'center', background: '#0f172a', borderRadius: '6px', border: '1px solid #334155' }}>
//                 <div className="loading-spinner"></div>
//                 <p style={{ color: '#38bdf8', marginTop: '0.75rem', fontWeight: 500 }}>
//                   Claude analyzing feature weights and formulating diagnostic brief...
//                 </p>
//               </div>
//             ) : aiError ? (
//               <div style={{ padding: '1rem', background: '#450a0a', color: '#fca5a5', borderRadius: '6px' }}>
//                 <strong>Explanation Error:</strong> {aiError}
//                 <button 
//                   onClick={handleRunAgentInvestigation}
//                   style={{ marginLeft: '1rem', padding: '0.3rem 0.6rem', background: '#991b1b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
//                 >
//                   Retry
//                 </button>
//               </div>
//             ) : aiReport ? (
//               <div className="ai-stub-card" style={{ background: '#0f172a', padding: '1.5rem', borderRadius: '8px', border: '1px solid #334155' }}>
//                 <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #1e293b', paddingBottom: '0.85rem', marginBottom: '1.25rem' }}>
//                   <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
//                     <span style={{ fontSize: '1.2rem' }}>🤖</span>
//                     <span style={{ fontWeight: 700, color: '#f8fafc', fontSize: '1.05rem' }}>
//                       Claude Diagnostic Brief — Grid {prediction.grid_id}
//                     </span>
//                   </div>
//                   <span className={`status-tag ${prediction.risk_level === 'CRITICAL' ? 'tag-critical' : 'tag-low'}`}>
//                     VERDICT: {prediction.risk_level}
//                   </span>
//                 </div>

//                 {/* 4 C8 Sections */}
//                 {aiReport.narrative && (
//                   <div style={{ lineHeight: '1.6' }}>
//                     {aiReport.narrative.split('### ').filter(Boolean).map((sec, idx) => {
//                       const lines = sec.trim().split('\n');
//                       const title = lines[0].trim();
//                       const content = lines.slice(1).join('\n').trim();

//                       const borderColor = title.includes('SEVERITY') 
//                         ? (prediction.risk_level === 'CRITICAL' ? '#ef4444' : '#38bdf8')
//                         : title.includes('EVIDENCE') 
//                         ? '#3b82f6' 
//                         : title.includes('INTERPRETATION') 
//                         ? '#a855f7' 
//                         : '#10b981';

//                       return (
//                         <div key={idx} style={{ marginBottom: '1rem', background: '#131d31', padding: '1rem 1.25rem', borderRadius: '6px', borderLeft: `4px solid ${borderColor}`, borderTop: '1px solid #1e293b', borderRight: '1px solid #1e293b', borderBottom: '1px solid #1e293b' }}>
//                           <h4 style={{ color: borderColor, margin: '0 0 0.5rem 0', fontSize: '0.92rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
//                             {title}
//                           </h4>
//                           <div style={{ fontSize: '0.88rem', color: '#cbd5e1' }}>
//                             {content.split('\n').map((line, lIdx) => {
//                               const trimmed = line.trim();
//                               if (!trimmed) return null;
//                               if (trimmed.startsWith('-') || trimmed.startsWith('•') || /^\d+\./.test(trimmed)) {
//                                 return (
//                                   <div key={lIdx} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.3rem' }}>
//                                     <span style={{ color: borderColor }}>›</span>
//                                     <div dangerouslySetInnerHTML={{ 
//                                       __html: trimmed.replace(/^[-•\d.]+\s*/, '')
//                                         .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #f8fafc">$1</strong>')
//                                         .replace(/`(.*?)`/g, '<code style="background: #1e293b; padding: 1px 5px; border-radius: 3px; color: #f59e0b">$1</code>')
//                                     }} />
//                                   </div>
//                                 );
//                               }
//                               return (
//                                 <p key={lIdx} style={{ margin: '0 0 0.4rem 0' }}
//                                   dangerouslySetInnerHTML={{ 
//                                     __html: trimmed
//                                       .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #f8fafc">$1</strong>')
//                                       .replace(/`(.*?)`/g, '<code style="background: #1e293b; padding: 1px 5px; border-radius: 3px; color: #f59e0b">$1</code>')
//                                   }} 
//                                 />
//                               );
//                             })}
//                           </div>
//                         </div>
//                       );
//                     })}
//                   </div>
//                 )}
//               </div>
//             ) : null}
//           </div>
//         </div>

//       </div>
//     </div>
//   );
// }






















import React, { useState, useEffect } from 'react';
import { predictNetworkRisk, explainRiskWithClaude } from '../api';
import StatusBanner from '../components/StatusBanner';

export default function PredictiveRisk({ defaultGridId }) {
  const [gridIdInput, setGridIdInput] = useState(defaultGridId ? String(defaultGridId) : '5161');
  const [timestampInput, setTimestampInput] = useState('2013-11-07T15:00');

  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Claude Agent States
  const [aiExplainActive, setAiExplainActive] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiReport, setAiReport] = useState(null);
  const [aiError, setAiError] = useState(null);

  const handlePredict = async (e) => {
    if (e) e.preventDefault();

    const idNum = parseInt(gridIdInput, 10);
    if (isNaN(idNum) || idNum < 1 || idNum > 10000) {
      setError('Please provide a valid Grid ID between 1 and 10000.');
      return;
    }

    if (!timestampInput) {
      setError('Please select an operational cutoff timestamp.');
      return;
    }

    setLoading(true);
    setError(null);
    setAiExplainActive(false);
    setAiReport(null);
    setAiError(null);

    try {
      const formattedTs = timestampInput.length === 16 ? `${timestampInput}:00` : timestampInput;
      const res = await predictNetworkRisk({
        grid_id: idNum,
        timestamp: formattedTs
      });
      setPrediction(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRunAgentInvestigation = async () => {
    if (!prediction) return;
    setAiExplainActive(true);
    setAiLoading(true);
    setAiError(null);

    const featObj = prediction.features_used || prediction.features || {};
    const riskScoreVal = prediction.risk_score ?? prediction.probability ?? prediction.risk_probability ?? 0;

    try {
      const payload = {
        grid_id: prediction.grid_id,
        timestamp: timestampInput,
        risk_score: riskScoreVal,
        risk_level: prediction.risk_level,
        features: featObj
      };
      const res = await explainRiskWithClaude(payload);
      setAiReport(res);
    } catch (err) {
      setAiError(err.message);
    } finally {
      setAiLoading(false);
    }
  };

  useEffect(() => {
    handlePredict();
  }, []);

  const getRiskBadgeClass = (level) => {
    if (level === 'CRITICAL') return 'tag-critical';
    if (level === 'ELEVATED') return 'tag-elevated';
    return 'tag-low';
  };

  // Safe accessor fallbacks across schema variations
  const currentRiskScore = prediction
    ? (prediction.risk_score ?? prediction.probability ?? prediction.risk_probability ?? 0)
    : 0;

  const currentFeatures = prediction
    ? (prediction.features_used || prediction.features || {})
    : null;

  const optimalCutoff = prediction?.optimal_threshold 
    ? (prediction.optimal_threshold * 100).toFixed(1) 
    : '70.5';

  return (
    <div className="overview-page">
      <div className="page-header">
        <div>
          <h2>Predictive Operational Risk View</h2>
          <p className="sub-header-desc">
            Point-in-time demand surge prediction: Gradient Boosted Decision Trees (HistGradientBoosting) evaluated against learned optimal cutoffs, paired with autonomous Claude agent root-cause investigation.
          </p>
        </div>
      </div>

      <StatusBanner error={error} onRetry={handlePredict} />

      {/* Snapshot Coordinates Input Panel */}
      <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem', background: '#1e293b', borderRadius: '8px' }}>
        <h4 style={{ margin: '0 0 0.75rem 0', color: '#93c5fd' }}>Operational Snapshot Coordinates</h4>
        <form onSubmit={handlePredict} style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'flex-end' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
              Grid ID (1–10000)
            </label>
            <input 
              type="number"
              style={{ padding: '0.55rem', borderRadius: '4px', background: '#0f172a', color: '#fff', border: '1px solid #334155', width: '130px' }}
              value={gridIdInput}
              onChange={(e) => setGridIdInput(e.target.value)}
              min="1"
              max="10000"
              required
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', color: '#94a3b8', marginBottom: '0.25rem' }}>
              Snapshot Cutoff (t)
            </label>
            <input 
              type="datetime-local"
              style={{ padding: '0.55rem', borderRadius: '4px', background: '#0f172a', color: '#fff', border: '1px solid #334155' }}
              value={timestampInput}
              onChange={(e) => setTimestampInput(e.target.value)}
              required
            />
          </div>

          <button 
            type="submit"
            style={{ padding: '0.6rem 1.4rem', borderRadius: '4px', background: '#2563eb', color: '#fff', border: 'none', cursor: 'pointer', fontWeight: 600 }}
            disabled={loading}
          >
            {loading ? 'Analyzing Telemetry...' : '⚡ Evaluate Surge Risk at t+1'}
          </button>
        </form>
      </div>

      {/* Loading Indicator */}
      {loading && !prediction && (
        <div className="state-container" style={{ padding: '2rem', textAlign: 'center' }}>
          <div className="loading-spinner"></div>
          <p style={{ color: '#94a3b8', marginTop: '1rem' }}>Extracting trailing telemetry & computing tree-model inference...</p>
        </div>
      )}

      {}
      <div className="prediction-output-column">
        
        {/* REGION A: PURE ML MODEL OUTPUT */}
        <div className="card-panel model-output-region">
          <div className="region-tag">HIST GRADIENT BOOSTING CLASSIFIER (ROC-AUC: 0.94)</div>
          
          {prediction && (
            <div>
              <div className="score-hero">
                <div>
                  <span className="kpi-label">Surge Probability Index</span>
                  <div className="risk-score-value">
                    {(currentRiskScore * 100).toFixed(1)}%
                  </div>
                  <span className="subtext-note">
                    Model predicted likelihood of $\ge 35\%$ volume expansion in window t+1
                  </span>
                </div>

                <div className="risk-meta-block">
                  <span className="kpi-label">Classified Level</span>
                  <div>
                    <span className={`status-tag ${getRiskBadgeClass(prediction.risk_level)}`}>
                      {prediction.risk_level}
                    </span>
                  </div>

                  <div style={{ marginTop: '10px' }}>
                    <span className="kpi-label">Decision Threshold</span>
                    <div style={{ fontSize: '0.85rem', color: '#38bdf8', fontWeight: 600 }}>
                      Learned Cutoff: {optimalCutoff}%
                    </div>
                  </div>

                  {prediction.model_version && (
                    <div style={{ marginTop: '8px' }}>
                      <span className="kpi-label">Model Engine</span>
                      <div className="model-version-badge">
                        <code>{prediction.model_version}</code>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {prediction.explanation_note && (
                <div className="model-note-box" style={{ marginTop: '1rem' }}>
                  <strong>Model Diagnostic:</strong> {prediction.explanation_note}
                </div>
              )}

              {}
              {currentFeatures && (
                <div style={{ marginTop: '1.25rem' }}>
                  <h5 style={{ margin: '0 0 0.5rem 0', color: '#94a3b8' }}>
                    Evaluated Feature Dynamics (24h Rolling Lookback & Momentum):
                  </h5>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(135px, 1fr))', gap: '0.75rem' }}>
                    <div className="kpi-mini-card">
                      <span className="mini-label">Avg Activity</span>
                      <span className="mini-value">
                        {typeof currentFeatures.avg_activity === 'number' 
                          ? currentFeatures.avg_activity.toLocaleString() 
                          : currentFeatures.avg_activity}
                      </span>
                    </div>

                    {/* Immediate Short-Term Momentum */}
                    {currentFeatures.immediate_ratio !== undefined && (
                      <div className="kpi-mini-card" style={{ borderColor: '#38bdf8' }}>
                        <span className="mini-label" style={{ color: '#38bdf8' }}>Immediate Ratio</span>
                        <span className="mini-value" style={{ color: '#38bdf8' }}>
                          {currentFeatures.immediate_ratio}x
                        </span>
                      </div>
                    )}

                    <div className="kpi-mini-card">
                      <span className="mini-label">Growth Rate</span>
                      <span className="mini-value">
                        {currentFeatures.activity_growth > 0 
                          ? `+${currentFeatures.activity_growth}` 
                          : currentFeatures.activity_growth}
                      </span>
                    </div>

                    <div className="kpi-mini-card">
                      <span className="mini-label">Peak Ratio</span>
                      <span className="mini-value">{currentFeatures.peak_ratio}x</span>
                    </div>

                    <div className="kpi-mini-card">
                      <span className="mini-label">Variability</span>
                      <span className="mini-value">{currentFeatures.variability}</span>
                    </div>

                    <div className="kpi-mini-card">
                      <span className="mini-label">Active Hours</span>
                      <span className="mini-value">{currentFeatures.active_hours}h</span>
                    </div>

                    <div className="kpi-mini-card">
                      <span className="mini-label">Data Share</span>
                      <span className="mini-value">
                        {(currentFeatures.internet_share * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {}
        <div className="card-panel narrative-explanation-region" style={{ marginTop: '1.5rem' }}>
          <div className="region-tag ai-tag">CLAUDE AI INVESTIGATION AGENT (RCA ENGINE)</div>
          
          <div className="ai-placeholder-content">
            <h4>Diagnostic Narrative & Root Cause Reasoning</h4>
            <p className="ai-desc">
              Cross-references evaluated feature dynamics against multi-channel anomaly z-scores to explain <em>why</em> this surge risk was flagged.
            </p>

            {!aiExplainActive ? (
              <button 
                className="ai-action-btn"
                onClick={handleRunAgentInvestigation}
                disabled={!prediction || loading}
                style={{ padding: '0.65rem 1.25rem', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 600 }}
              >
                ✨ Explain with AI (Claude Agent)
              </button>
            ) : aiLoading ? (
              <div style={{ padding: '1.5rem', textAlign: 'center', background: '#0f172a', borderRadius: '6px', border: '1px solid #334155' }}>
                <div className="loading-spinner"></div>
                <p style={{ color: '#38bdf8', marginTop: '0.75rem', fontWeight: 500 }}>
                  Claude querying anomaly tools and formulating root-cause brief...
                </p>
              </div>
            ) : aiError ? (
              <div style={{ padding: '1rem', background: '#450a0a', color: '#fca5a5', borderRadius: '6px' }}>
                <strong>Explanation Error:</strong> {aiError}
                <button 
                  onClick={handleRunAgentInvestigation}
                  style={{ marginLeft: '1rem', padding: '0.3rem 0.6rem', background: '#991b1b', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                >
                  Retry
                </button>
              </div>
            ) : aiReport ? (
              <div className="ai-stub-card" style={{ background: '#0f172a', padding: '1.5rem', borderRadius: '8px', border: '1px solid #334155' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #1e293b', paddingBottom: '0.85rem', marginBottom: '1.25rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <span style={{ fontSize: '1.2rem' }}>🤖</span>
                    <span style={{ fontWeight: 700, color: '#f8fafc', fontSize: '1.05rem' }}>
                      Claude Diagnostic Brief — Grid {prediction.grid_id}
                    </span>
                  </div>
                  <span className={`status-tag ${prediction.risk_level === 'CRITICAL' ? 'tag-critical' : 'tag-low'}`}>
                    VERDICT: {prediction.risk_level}
                  </span>
                </div>

                {/* Structured Sections */}
                {aiReport.narrative && (
                  <div style={{ lineHeight: '1.6' }}>
                    {aiReport.narrative.split('### ').filter(Boolean).map((sec, idx) => {
                      const lines = sec.trim().split('\n');
                      const title = lines[0].trim();
                      const content = lines.slice(1).join('\n').trim();

                      const borderColor = title.includes('SEVERITY') 
                        ? (prediction.risk_level === 'CRITICAL' ? '#ef4444' : '#38bdf8')
                        : title.includes('EVIDENCE') 
                        ? '#3b82f6' 
                        : title.includes('INTERPRETATION') 
                        ? '#a855f7' 
                        : '#10b981';

                      return (
                        <div key={idx} style={{ marginBottom: '1rem', background: '#131d31', padding: '1rem 1.25rem', borderRadius: '6px', borderLeft: `4px solid ${borderColor}`, borderTop: '1px solid #1e293b', borderRight: '1px solid #1e293b', borderBottom: '1px solid #1e293b' }}>
                          <h4 style={{ color: borderColor, margin: '0 0 0.5rem 0', fontSize: '0.92rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                            {title}
                          </h4>
                          <div style={{ fontSize: '0.88rem', color: '#cbd5e1' }}>
                            {content.split('\n').map((line, lIdx) => {
                              const trimmed = line.trim();
                              if (!trimmed) return null;
                              if (trimmed.startsWith('-') || trimmed.startsWith('•') || /^\d+\./.test(trimmed)) {
                                return (
                                  <div key={lIdx} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.3rem' }}>
                                    <span style={{ color: borderColor }}>›</span>
                                    <div dangerouslySetInnerHTML={{ 
                                      __html: trimmed.replace(/^[-•\d.]+\s*/, '')
                                        .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #f8fafc">$1</strong>')
                                        .replace(/`(.*?)`/g, '<code style="background: #1e293b; padding: 1px 5px; border-radius: 3px; color: #f59e0b">$1</code>')
                                    }} />
                                  </div>
                                );
                              }
                              return (
                                <p key={lIdx} style={{ margin: '0 0 0.4rem 0' }}
                                  dangerouslySetInnerHTML={{ 
                                    __html: trimmed
                                      .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #f8fafc">$1</strong>')
                                      .replace(/`(.*?)`/g, '<code style="background: #1e293b; padding: 1px 5px; border-radius: 3px; color: #f59e0b">$1</code>')
                                  }} 
                                />
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>

      </div>
    </div>
  );
}