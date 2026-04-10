const styles = {
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 6,
  },
  hours: {
    fontSize: 22,
    fontWeight: 700,
  },
  target: {
    fontSize: 14,
    color: 'var(--text-muted)',
  },
  track: {
    height: 8,
    background: 'var(--surface2)',
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 8,
  },
  fill: {
    height: '100%',
    borderRadius: 4,
    transition: 'width 0.4s ease',
  },
  meta: {
    display: 'flex',
    gap: 16,
    fontSize: 13,
    color: 'var(--text-muted)',
  },
}

export default function WeeklyProgress({ context }) {
  const { total_hours, hour_target, ride_count, total_tss, days_remaining_in_week } = context
  const pct = Math.min(100, (total_hours / hour_target) * 100)
  const fillColor = pct >= 100 ? 'var(--green)' : pct > 60 ? 'var(--blue)' : 'var(--text-muted)'

  return (
    <div>
      <div style={styles.row}>
        <span style={styles.hours}>{total_hours.toFixed(1)} h</span>
        <span style={styles.target}>/ {hour_target} h target</span>
      </div>
      <div style={styles.track}>
        <div style={{ ...styles.fill, width: `${pct}%`, background: fillColor }} />
      </div>
      <div style={styles.meta}>
        <span>{ride_count} ride{ride_count !== 1 ? 's' : ''}</span>
        <span>TSS {total_tss.toFixed(0)}</span>
        <span>{days_remaining_in_week}d left</span>
      </div>
    </div>
  )
}
