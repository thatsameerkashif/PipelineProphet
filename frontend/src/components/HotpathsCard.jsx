function rateColor(r) {
  if (r >= 0.6) return '#dc2626';
  if (r >= 0.35) return '#d97706';
  return '#16a34a';
}

export default function HotpathsCard({ hotpaths = [] }) {
  return (
    <div className="card">
      <div style={{ marginBottom: 12 }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>Build DNA: Failure Hotspot Files</div>
        <div style={{ fontSize: 12, color: '#57606a', marginTop: 2 }}>
          Files most correlated with pipeline failures in this repository
        </div>
      </div>

      {hotpaths.length === 0 ? (
        <div style={{ textAlign: 'center', color: '#9ca3af', padding: '20px 0', fontStyle: 'italic' }}>
          No hotpath data available yet
        </div>
      ) : (
        <div>
          {hotpaths.map((hp, i) => {
            const pct = Math.round((hp.failure_rate ?? 0) * 100);
            const color = rateColor(hp.failure_rate ?? 0);
            return (
              <div
                key={i}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr auto auto',
                  gap: '8px 12px',
                  alignItems: 'center',
                  padding: '8px 0',
                  borderBottom: i < hotpaths.length - 1 ? '1px solid #f3f4f6' : 'none',
                }}
              >
                {/* File path */}
                <div style={{ overflow: 'hidden' }}>
                  <code style={{ fontFamily: 'monospace', fontSize: 12, color: '#1f2328' }}>
                    {hp.file_path}
                  </code>
                  <div className="progress-bar-track" style={{ marginTop: 4 }}>
                    <div
                      className="progress-bar-fill"
                      style={{ width: `${pct}%`, background: color }}
                    />
                  </div>
                </div>

                {/* Failure rate */}
                <span style={{ fontWeight: 700, fontSize: 14, color, whiteSpace: 'nowrap' }}>
                  {pct}%
                </span>

                {/* Run count */}
                <span style={{ fontSize: 12, color: '#9ca3af', whiteSpace: 'nowrap' }}>
                  {hp.total_runs} runs
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
