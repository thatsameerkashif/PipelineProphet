import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ReferenceDot,
  ResponsiveContainer,
} from 'recharts';

/**
 * Split data into three colour-coded segments by MAE threshold.
 * Points in the boundary zones appear in both adjacent segments so the
 * lines connect without gaps.
 */
function splitByMae(data) {
  const red    = [];  // MAE > 0.35
  const amber  = [];  // 0.25 <= MAE <= 0.35
  const green  = [];  // MAE < 0.25

  for (let i = 0; i < data.length; i++) {
    const pt = data[i];
    const mae = pt.mae;

    if (mae > 0.35) {
      red.push(pt);
      // stitch to amber if next point is amber/green
      if (i + 1 < data.length && data[i + 1].mae <= 0.35) amber.push(pt);
    } else if (mae >= 0.25) {
      amber.push(pt);
      // stitch downward
      if (i + 1 < data.length && data[i + 1].mae < 0.25) green.push(pt);
      // stitch upward
      if (i > 0 && data[i - 1].mae > 0.35) red.push(pt);
    } else {
      green.push(pt);
      if (i > 0 && data[i - 1].mae >= 0.25) amber.push(pt);
    }
  }

  return { red, amber, green };
}

/** Find first point where MAE drops below 0.25. */
function findCrossoverPoint(data) {
  for (const pt of data) {
    if (pt.mae < 0.25) return pt;
  }
  return null;
}

/** Custom tooltip */
function CustomTooltip({ active, payload }) {
  if (!active || !payload || !payload.length) return null;
  const { build_index, mae } = payload[0].payload;
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #e5e7eb',
      borderRadius: 6,
      padding: '6px 10px',
      fontSize: 12,
    }}>
      <strong>Build #{build_index}</strong>: MAE = {mae.toFixed(3)}
    </div>
  );
}

export default function AccuracyChart({ data = [] }) {
  const { red, amber, green } = splitByMae(data);
  const crossover = findCrossoverPoint(data);

  return (
    <div className="card">
      <div style={{ marginBottom: 4 }}>
        <div style={{ fontWeight: 700, fontSize: 15 }}>Research Output: Accuracy Feedback Loop</div>
        <div style={{ fontWeight: 600, fontSize: 13, color: '#1f2328', marginTop: 6 }}>
          Prediction Accuracy Improves with Build History
        </div>
        <div style={{ fontSize: 12, color: '#57606a', marginTop: 2 }}>
          Mean Absolute Error of stage-level failure probability forecasts
        </div>
      </div>

      {data.length === 0 ? (
        <div style={{ textAlign: 'center', color: '#9ca3af', padding: '32px 0', fontStyle: 'italic' }}>
          No accuracy data available yet
        </div>
      ) : (
        <div style={{ marginTop: 16 }}>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart margin={{ top: 10, right: 30, left: 0, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
              <XAxis
                dataKey="history_depth"
                type="number"
                domain={['dataMin', 'dataMax']}
                allowDuplicatedCategory={false}
                label={{ value: 'Build History Depth', position: 'insideBottom', offset: -4, fontSize: 12, fill: '#57606a' }}
                tick={{ fontSize: 11, fill: '#57606a' }}
              />
              <YAxis
                domain={[0, 0.5]}
                label={{ value: 'Prediction Error (MAE)', angle: -90, position: 'insideLeft', offset: 10, fontSize: 12, fill: '#57606a' }}
                tick={{ fontSize: 11, fill: '#57606a' }}
              />
              <Tooltip content={<CustomTooltip />} />

              {/* Reference lines */}
              <ReferenceLine
                y={0.5}
                stroke="#dc2626"
                strokeDasharray="5 3"
                label={{ value: 'Random Baseline (0.50)', position: 'insideTopRight', fontSize: 11, fill: '#dc2626' }}
              />
              <ReferenceLine
                y={0.25}
                stroke="#16a34a"
                strokeDasharray="5 3"
                label={{ value: 'Good Prediction Threshold (0.25)', position: 'insideTopRight', fontSize: 11, fill: '#16a34a' }}
              />

              {/* Crossover annotation */}
              {crossover && (
                <ReferenceDot
                  x={crossover.history_depth}
                  y={crossover.mae}
                  r={5}
                  fill="#16a34a"
                  stroke="#fff"
                  strokeWidth={2}
                  label={{ value: 'History pays off →', position: 'right', fontSize: 11, fill: '#16a34a' }}
                />
              )}

              {/* Three coloured line segments */}
              <Line
                data={red}
                type="monotone"
                dataKey="mae"
                stroke="#dc2626"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                isAnimationActive={false}
              />
              <Line
                data={amber}
                type="monotone"
                dataKey="mae"
                stroke="#d97706"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                isAnimationActive={false}
              />
              <Line
                data={green}
                type="monotone"
                dataKey="mae"
                stroke="#16a34a"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>

          {/* Legend */}
          <div style={{ display: 'flex', gap: 16, justifyContent: 'center', fontSize: 11, color: '#57606a', marginTop: 4 }}>
            <span><span style={{ color: '#dc2626', fontWeight: 700 }}>■</span> MAE &gt; 0.35 (poor)</span>
            <span><span style={{ color: '#d97706', fontWeight: 700 }}>■</span> MAE 0.25–0.35 (improving)</span>
            <span><span style={{ color: '#16a34a', fontWeight: 700 }}>■</span> MAE &lt; 0.25 (good)</span>
          </div>
        </div>
      )}
    </div>
  );
}
