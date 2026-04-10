const intensityColors = {
  recovery: 'var(--blue)',
  z2: 'var(--green)',
  tempo: 'var(--yellow)',
  threshold: 'var(--orange)',
  rest: 'var(--text-muted)',
}

const intensityLabels = {
  recovery: 'Recovery',
  z2: 'Endurance Z2',
  tempo: 'Tempo / Sweet Spot',
  threshold: 'Threshold',
  rest: 'Rest Day',
}

const styles = {
  card: {
    background: 'var(--surface)',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderLeft: '3px solid var(--green)',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  label: {
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--text-muted)',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  badge: {
    fontSize: 12,
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: 10,
    background: 'var(--surface2)',
  },
  description: {
    fontSize: 15,
    fontWeight: 500,
    lineHeight: 1.4,
    marginBottom: 8,
  },
  powerTarget: {
    fontSize: 13,
    color: 'var(--text-muted)',
    fontFamily: 'monospace',
    marginBottom: 8,
  },
  rationale: {
    fontSize: 13,
    color: 'var(--text-muted)',
    lineHeight: 1.4,
    borderTop: '1px solid var(--border)',
    paddingTop: 8,
    marginTop: 4,
  },
}

export default function NextWorkout({ workout }) {
  const color = intensityColors[workout.type] || 'var(--text-muted)'
  const typeLabel = intensityLabels[workout.type] || workout.type

  return (
    <div style={{ ...styles.card, borderLeftColor: color }}>
      <div style={styles.header}>
        <span style={styles.label}>Next Workout</span>
        <span style={{ ...styles.badge, color }}>{typeLabel}</span>
      </div>
      <div style={styles.description}>{workout.description}</div>
      {workout.power_target && workout.power_target !== '—' && (
        <div style={styles.powerTarget}>{workout.power_target}</div>
      )}
      <div style={styles.rationale}>{workout.rationale}</div>
    </div>
  )
}
