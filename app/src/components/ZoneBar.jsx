const ZONE_COLORS = {
  z1: '#6b7280', // gray
  z2: '#4ade80', // green
  z3: '#facc15', // yellow
  z4: '#fb923c', // orange
  z5: '#f87171', // red
  z6: '#c084fc', // purple
}

const ZONE_LABELS = { z1: 'Z1', z2: 'Z2', z3: 'Z3', z4: 'Z4', z5: 'Z5', z6: 'Z6' }

const styles = {
  bar: {
    display: 'flex',
    height: 20,
    borderRadius: 6,
    overflow: 'hidden',
    gap: 1,
    marginBottom: 8,
  },
  legend: {
    display: 'flex',
    gap: 10,
    flexWrap: 'wrap',
    marginTop: 4,
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    fontSize: 12,
    color: 'var(--text-muted)',
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
    flexShrink: 0,
  },
}

export default function ZoneBar({ zones }) {
  const keys = ['z1', 'z2', 'z3', 'z4', 'z5', 'z6']
  const minutes_key = k => `${k}_minutes`

  const total = keys.reduce((sum, k) => sum + (zones[minutes_key(k)] || 0), 0)
  if (total === 0) return null

  return (
    <div>
      <div style={styles.bar}>
        {keys.map(k => {
          const mins = zones[minutes_key(k)] || 0
          const pct = (mins / total) * 100
          if (pct < 0.5) return null
          return (
            <div
              key={k}
              style={{
                width: `${pct}%`,
                background: ZONE_COLORS[k],
                minWidth: 2,
              }}
              title={`${ZONE_LABELS[k]}: ${mins.toFixed(1)} min`}
            />
          )
        })}
      </div>
      <div style={styles.legend}>
        {keys.map(k => {
          const mins = zones[minutes_key(k)] || 0
          if (mins < 0.1) return null
          return (
            <div key={k} style={styles.legendItem}>
              <div style={{ ...styles.legendDot, background: ZONE_COLORS[k] }} />
              {ZONE_LABELS[k]} {mins.toFixed(0)}m
            </div>
          )
        })}
      </div>
    </div>
  )
}
