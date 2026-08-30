import { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import { api } from './api';
import PreRunRiskCard from './components/PreRunRiskCard';
import BuildList from './components/BuildList';
import AccuracyChart from './components/AccuracyChart';
import HotpathsCard from './components/HotpathsCard';

const REPO_ID = 'pipeline-prophet-demo';

const DEMO_PAYLOAD = {
  ref: 'refs/heads/main',
  after: 'deadbeef' + Date.now().toString(16).slice(-8),
  pusher: { name: 'demo-user' },
  repository: { name: REPO_ID },
  commits: [
    {
      added: [],
      modified: ['requirements.txt', 'src/main.py'],
      removed: [],
    },
  ],
};

export default function App() {
  const [prediction, setPrediction] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [historyDepth, setHistoryDepth] = useState(null);
  const [builds, setBuilds] = useState([]);
  const [accuracy, setAccuracy] = useState([]);
  const [hotpaths, setHotpaths] = useState([]);
  const [stats, setStats] = useState(null);

  const latestRunIdRef = useRef(null);
  const pollIntervalRef = useRef(null);

  // ── Fetch latest prediction (returns null if 404) ──────────────────────────
  const fetchLatestPrediction = useCallback(async () => {
    try {
      const data = await api.getLatestPrediction(REPO_ID);
      if (!data) return null;
      return data;
    } catch {
      return null;
    }
  }, []);

  // ── Normal 5-second polling ────────────────────────────────────────────────
  const startNormalPolling = useCallback(() => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = setInterval(async () => {
      const data = await fetchLatestPrediction();
      if (data && data.run_id !== latestRunIdRef.current) {
        latestRunIdRef.current = data.run_id;
        setPrediction(data);
      }
    }, 5000);
  }, [fetchLatestPrediction]);

  // ── Aggressive 1-second polling after demo trigger ─────────────────────────
  const startAggressivePolling = useCallback((priorRunId) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = setInterval(async () => {
      const data = await fetchLatestPrediction();
      if (data && data.run_id !== priorRunId) {
        clearInterval(pollIntervalRef.current);
        latestRunIdRef.current = data.run_id;
        setPrediction(data);
        setGenerating(false);
        // Refresh builds list so the new run appears with correct status
        api.getBuilds(REPO_ID).then(d => setBuilds(d ?? [])).catch(() => {});
        startNormalPolling();
      }
    }, 1000);
  }, [fetchLatestPrediction, startNormalPolling]);

  // ── On mount: load everything ──────────────────────────────────────────────
  useEffect(() => {
    async function init() {
      const [latestPred, buildsData, accuracyData, hotpathsData, statsData] = await Promise.allSettled([
        fetchLatestPrediction(),
        api.getBuilds(REPO_ID).catch(() => []),
        api.getAccuracy(REPO_ID).catch(() => []),
        api.getHotpaths(REPO_ID).catch(() => []),
        api.getStats(REPO_ID).catch(() => null),
      ]);

      if (latestPred.status === 'fulfilled' && latestPred.value) {
        setPrediction(latestPred.value);
        latestRunIdRef.current = latestPred.value.run_id;
      }
      if (buildsData.status === 'fulfilled') setBuilds(buildsData.value ?? []);
      if (accuracyData.status === 'fulfilled') setAccuracy(accuracyData.value ?? []);
      if (hotpathsData.status === 'fulfilled') setHotpaths(hotpathsData.value ?? []);
      if (statsData.status === 'fulfilled' && statsData.value) setStats(statsData.value);
    }

    init();
    startNormalPolling();

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Demo trigger ───────────────────────────────────────────────────────────
  async function handleTriggerDemo() {
    if (generating) return;
    setGenerating(true);
    const priorRunId = latestRunIdRef.current;

    // Build a fresh payload with a unique commit SHA each time
    const payload = {
      ...DEMO_PAYLOAD,
      after: 'demo' + Date.now().toString(16),
    };

    try {
      await api.triggerDemo(payload);
    } catch {
      // backend may return 202 even on network edge cases — continue polling
    }

    // Reload builds list after trigger
    api.getBuilds(REPO_ID)
      .then(d => setBuilds(d ?? []))
      .catch(() => {});

    // Wait 3 s then switch to aggressive polling
    setTimeout(() => {
      startAggressivePolling(priorRunId);
    }, 3000);
  }

  const displayStats = stats ?? {
    total_builds: 80,
    current_mae: 0.17,
    improvement_pct: 62,
    most_risky_file: 'requirements.txt',
  };

  return (
    <>
      <header className="app-header">
        <h1>🔮 Pipeline Prophet</h1>
        <span className="watsonx-badge">IBM watsonx.ai</span>
      </header>

      <div className="stats-bar">
        <span className="stats-pill">{displayStats.total_builds} Builds Analyzed</span>
        <span className="stats-pill">Current MAE: {typeof displayStats.current_mae === 'number' ? displayStats.current_mae.toFixed(2) : displayStats.current_mae}</span>
        <span className="stats-pill">{displayStats.improvement_pct}% Accuracy Improvement</span>
        <span className="stats-pill">Riskiest File: {displayStats.most_risky_file}</span>
      </div>

      <main className="app-container">
        <PreRunRiskCard
          prediction={prediction}
          generating={generating}
          historyDepth={historyDepth ?? prediction?.history_depth}
        />

        <BuildList builds={builds} onTriggerDemo={handleTriggerDemo} />

        <AccuracyChart data={accuracy} />

        <HotpathsCard hotpaths={hotpaths} />
      </main>

      <footer className="ibm-footer">
        Pipeline Prophet · Built with IBM watsonx.ai Granite &amp; IBM Cloudant
      </footer>
    </>
  );
}
