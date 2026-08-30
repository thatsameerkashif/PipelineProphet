import { useState } from 'react';
import { api } from '../api';

function formatDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  if (isNaN(d)) return ts;
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function StatusBadge({ status }) {
  const s = (status ?? '').toLowerCase();
  const styles = {
    passed:    { background: '#f0fdf4', color: '#16a34a', border: '1px solid #86efac' },
    failed:    { background: '#fef2f2', color: '#dc2626', border: '1px solid #fca5a5' },
    pending:   { background: '#fffbeb', color: '#d97706', border: '1px solid #fcd34d' },
    predicted: { background: '#eff6ff', color: '#2563eb', border: '1px solid #93c5fd' },
    skipped:   { background: '#f3f4f6', color: '#6b7280', border: '1px solid #d1d5db' },
  };
  const style = styles[s] ?? styles.pending;
  return (
    <span style={{ ...style, padding: '1px 8px', borderRadius: 10, fontWeight: 600, fontSize: 11 }}>
      {s === 'predicted' ? 'PREDICTED' : s.toUpperCase() || 'PENDING'}
    </span>
  );
}

function BuildDetailModal({ runId, onClose }) {
  const [build, setBuild] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [loading, setLoading] = useState(true);

  useState(() => {
    async function load() {
      try {
        const [b, p] = await Promise.allSettled([
          api.getBuild(runId),
          api.getBuildPrediction(runId),
        ]);
        if (b.status === 'fulfilled') setBuild(b.value);
        if (p.status === 'fulfilled') setPrediction(p.value);
      } finally {
        setLoading(false);
      }
    }
    load();
  });

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        background: 'white', borderRadius: 10, padding: 28, width: 560, maxWidth: '95vw',
        maxHeight: '85vh', overflowY: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }} onClick={e => e.stopPropagation()}>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <span style={{ fontWeight: 700, fontSize: 16 }}>Build Detail</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 20, cursor: 'pointer', color: '#6b7280' }}>✕</button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#9ca3af' }}>Loading…</div>
        ) : (
          <>
            {build && (
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 8 }}>BUILD RUN</div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 16px', fontSize: 13 }}>
                  <div><span style={{ color: '#9ca3af' }}>Commit: </span><code style={{ background: '#f3f4f6', padding: '1px 4px', borderRadius: 3 }}>{(build.commit_sha ?? '').slice(0, 12)}</code></div>
                  <div><span style={{ color: '#9ca3af' }}>Author: </span>{build.author ?? '—'}</div>
                  <div><span style={{ color: '#9ca3af' }}>Branch: </span><strong>{build.branch ?? 'main'}</strong></div>
                  <div><span style={{ color: '#9ca3af' }}>Status: </span><StatusBadge status={build.status ?? build.outcome} /></div>
                  <div style={{ gridColumn: '1/-1' }}><span style={{ color: '#9ca3af' }}>Started: </span>{formatDate(build.started_at)}</div>
                  {build.changed_files?.length > 0 && (
                    <div style={{ gridColumn: '1/-1' }}>
                      <span style={{ color: '#9ca3af' }}>Changed files: </span>
                      {build.changed_files.map(f => (
                        <code key={f} style={{ background: '#f3f4f6', padding: '1px 5px', borderRadius: 3, marginRight: 4, fontSize: 11 }}>{f}</code>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {prediction && (
              <div>
                <div style={{ fontSize: 12, color: '#9ca3af', marginBottom: 8 }}>PRE-RUN PREDICTION</div>
                <div style={{ marginBottom: 8 }}>
                  <span style={{ fontWeight: 600, marginRight: 8 }}>Overall Risk:</span>
                  <span style={{
                    padding: '2px 10px', borderRadius: 10, fontWeight: 700, fontSize: 12,
                    ...(prediction.overall_risk === 'HIGH' ? { background: '#fef2f2', color: '#dc2626' }
                      : prediction.overall_risk === 'LOW' ? { background: '#f0fdf4', color: '#16a34a' }
                      : { background: '#fffbeb', color: '#d97706' })
                  }}>{prediction.overall_risk}</span>
                </div>
                {Object.entries(prediction.stage_predictions ?? {}).map(([stage, sp]) => (
                  <div key={stage} style={{ marginBottom: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                      <span style={{ fontWeight: 600, textTransform: 'capitalize', fontSize: 13 }}>{stage}</span>
                      <span style={{ fontWeight: 700, fontSize: 13, color: sp.probability >= 0.6 ? '#dc2626' : sp.probability >= 0.3 ? '#d97706' : '#16a34a' }}>
                        {Math.round((sp.probability ?? 0) * 100)}%
                      </span>
                    </div>
                    <div style={{ background: '#f3f4f6', borderRadius: 4, height: 6, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${Math.round((sp.probability ?? 0) * 100)}%`, borderRadius: 4,
                        background: sp.probability >= 0.6 ? '#ef4444' : sp.probability >= 0.3 ? '#f59e0b' : '#22c55e' }} />
                    </div>
                    {sp.rationale && <div style={{ fontSize: 11, color: '#57606a', marginTop: 3 }}>{sp.rationale}</div>}
                  </div>
                ))}
                {prediction.summary && (
                  <div style={{ marginTop: 12, padding: '10px 12px', background: '#f7f8fa', borderRadius: 6, fontSize: 12, color: '#444', lineHeight: 1.6 }}>
                    {prediction.summary}
                  </div>
                )}
              </div>
            )}

            {!build && !prediction && (
              <div style={{ color: '#9ca3af', textAlign: 'center', padding: '20px 0' }}>No data available for this build.</div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function BuildList({ builds = [], onTriggerDemo }) {
  const [selectedRunId, setSelectedRunId] = useState(null);

  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <span style={{ fontWeight: 700, fontSize: 15 }}>Recent Builds</span>
        <button
          onClick={onTriggerDemo}
          style={{
            background: '#3b82d4', color: 'white', border: 'none',
            borderRadius: 6, padding: '6px 14px', fontWeight: 600, fontSize: 13, cursor: 'pointer',
          }}
        >
          ▶ Trigger Demo Push
        </button>
      </div>

      {builds.length === 0 ? (
        <div style={{ color: '#9ca3af', fontStyle: 'italic', textAlign: 'center', padding: '20px 0' }}>No builds yet</div>
      ) : (
        <table className="builds-table">
          <thead>
            <tr>
              <th>Commit</th><th>Author</th><th>Branch</th><th>Status</th><th>Started</th><th></th>
            </tr>
          </thead>
          <tbody>
            {builds.map((b) => (
              <tr key={b.run_id ?? b._id}>
                <td><code style={{ fontFamily: 'monospace', background: '#f3f4f6', padding: '1px 5px', borderRadius: 3, fontSize: 12 }}>
                  {(b.commit_sha ?? '').slice(0, 8)}
                </code></td>
                <td>{b.author ?? '—'}</td>
                <td style={{ color: '#57606a' }}>{b.branch ?? 'main'}</td>
                <td><StatusBadge status={b.status ?? b.outcome} /></td>
                <td style={{ color: '#57606a' }}>{formatDate(b.started_at ?? b.created_at)}</td>
                <td>
                  <span
                    onClick={() => setSelectedRunId(b.run_id ?? b._id)}
                    style={{ color: '#3b82d4', fontSize: 12, cursor: 'pointer', textDecoration: 'underline' }}
                  >
                    View
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selectedRunId && (
        <BuildDetailModal runId={selectedRunId} onClose={() => setSelectedRunId(null)} />
      )}
    </div>
  );
}
