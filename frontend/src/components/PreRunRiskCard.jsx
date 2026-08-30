const STAGES = ['install', 'test', 'lint', 'build'];

function riskClass(overall) {
  if (!overall) return 'badge-medium';
  const u = overall.toUpperCase();
  if (u === 'HIGH') return 'badge-high';
  if (u === 'LOW') return 'badge-low';
  return 'badge-medium';
}

function probClass(p) {
  if (p >= 0.6) return { text: '#dc2626', bar: 'progress-high' };
  if (p >= 0.3) return { text: '#d97706', bar: 'progress-medium' };
  return { text: '#16a34a', bar: 'progress-low' };
}

function short(sha) {
  return sha ? sha.slice(0, 8) : '--------';
}

function SkeletonCard({ generating, historyDepth }) {
  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <span style={{ fontWeight: 700, fontSize: 15 }}>Pre-Run Risk Analysis</span>
      </div>
      {generating ? (
        <div style={{ textAlign: 'center', padding: '32px 0', color: '#57606a' }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>⏳</div>
          <div style={{ fontWeight: 600 }}>
            Analyzing {historyDepth ? `${historyDepth} builds of` : ''} repository history…
          </div>
          <div style={{ fontSize: 12, marginTop: 6, color: '#9ca3af' }}>Powered by IBM watsonx.ai Granite</div>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '32px 0', color: '#57606a' }}>
          <div className="skeleton" style={{ height: 16, width: '60%', margin: '0 auto 10px' }} />
          <div className="skeleton" style={{ height: 12, width: '40%', margin: '0 auto 24px' }} />
          {STAGES.map(s => (
            <div key={s} style={{ marginBottom: 14 }}>
              <div className="skeleton" style={{ height: 12, width: '80%', margin: '0 auto 6px' }} />
              <div className="skeleton" style={{ height: 6, width: '80%', margin: '0 auto' }} />
            </div>
          ))}
          <div style={{ marginTop: 20, fontSize: 13, color: '#9ca3af', fontStyle: 'italic' }}>
            Waiting for next push event…
          </div>
        </div>
      )}
    </div>
  );
}

export default function PreRunRiskCard({ prediction, generating, historyDepth }) {
  if (!prediction) {
    return <SkeletonCard generating={generating} historyDepth={historyDepth} />;
  }

  const { commit_sha, overall_risk, summary, stage_predictions, history_depth } = prediction;

  // Normalise: backend may use "author" at top level but it might be nested
  const author = prediction.author ?? prediction.pusher ?? 'unknown';
  const branch = prediction.branch ?? 'main';

  return (
    <div className="card">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ fontWeight: 700, fontSize: 15 }}>Pre-Run Risk Analysis</span>
        <span className={riskClass(overall_risk)}>{overall_risk?.toUpperCase() ?? 'UNKNOWN'}</span>
      </div>

      {/* Commit info */}
      <div style={{ color: '#57606a', fontSize: 12, marginBottom: 4 }}>
        <code style={{ fontFamily: 'monospace', background: '#f3f4f6', padding: '1px 5px', borderRadius: 3 }}>
          {short(commit_sha)}
        </code>
        {' · '}{author}{' · '}<strong>{branch}</strong>
      </div>

      {/* Evidence line */}
      {history_depth != null && (
        <div style={{ fontSize: 12, color: '#9ca3af', fontStyle: 'italic', marginBottom: 16 }}>
          Based on {history_depth} builds of repository history
        </div>
      )}

      {/* Stage rows */}
      {STAGES.map(stage => {
        const sp = stage_predictions?.[stage];
        const prob = sp?.probability ?? 0;
        const rationale = sp?.rationale ?? '';
        const pct = Math.round(prob * 100);
        const { text, bar } = probClass(prob);

        return (
          <div key={stage} className="stage-row">
            <div className="stage-header">
              <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{stage}</span>
              <span style={{ fontWeight: 700, fontSize: 16, color: text }}>{pct}%</span>
            </div>
            <div className="progress-bar-track">
              <div
                className={`progress-bar-fill ${bar}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            {rationale && (
              <div style={{ fontSize: 12, color: '#57606a', marginTop: 3 }}>{rationale}</div>
            )}
          </div>
        );
      })}

      {/* AI Summary */}
      {summary && (
        <div style={{ marginTop: 16, padding: '12px 14px', background: '#f7f8fa', borderRadius: 6, border: '1px solid #e5e7eb' }}>
          <div style={{ fontWeight: 600, fontSize: 12, color: '#57606a', marginBottom: 4 }}>AI Analysis</div>
          <div style={{ fontSize: 13, lineHeight: 1.6 }}>{summary}</div>
        </div>
      )}

      {/* Footer */}
      <div style={{ marginTop: 14, fontSize: 11, color: '#9ca3af', textAlign: 'right' }}>
        Powered by IBM watsonx.ai Granite · Build DNA Store: IBM Cloudant
      </div>
    </div>
  );
}
