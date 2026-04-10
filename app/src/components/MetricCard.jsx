const styles = {
  card: {
    background: 'var(--surface)',
    borderRadius: 12,
    padding: '16px 14px',
    display: 'flex',
    flexDirection: 'column',
    gap: 4,
  },
  label: {
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--text-muted)',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  value: {
    fontSize: 28,
    fontWeight: 700,
    lineHeight: 1.1,
    color: 'var(--text)',
  },
  unit: {
    fontSize: 13,
    color: 'var(--text-muted)',
    fontWeight: 400,
    marginLeft: 2,
  },
}

export default function MetricCard({ label, value, unit }) {
  return (
    <div style={styles.card}>
      <div style={styles.label}>{label}</div>
      <div style={styles.value}>
        {value ?? '—'}
        {unit && value != null && <span style={styles.unit}>{unit}</span>}
      </div>
    </div>
  )
}
