import { useState } from 'react'

const HOUR_TARGET = 10

const styles = {
  empty: {
    textAlign: 'center',
    color: 'var(--text-muted)',
    fontSize: 14,
    padding: '40px 0',
  },
  weekCard: {
    background: 'var(--surface)',
    borderRadius: 12,
    marginBottom: 10,
    overflow: 'hidden',
  },
  weekRow: {
    display: 'grid',
    gridTemplateColumns: '2fr 1.2fr 1fr 1fr 1fr 1fr 1fr 1fr',
    alignItems: 'center',
    padding: '12px 14px',
    cursor: 'pointer',
    gap: 4,
  },
  colHeader: {
    fontSize: 10,
    fontWeight: 600,
    color: 'var(--text-muted)',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    padding: '8px 14px 4px',
    display: 'grid',
    gridTemplateColumns: '2fr 1.2fr 1fr 1fr 1fr 1fr 1fr 1fr',
    gap: 4,
  },
  cell: {
    fontSize: 13,
    fontWeight: 500,
    color: 'var(--text)',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  weekLabel: {
    fontSize: 13,
    fontWeight: 600,
    color: 'var(--text)',
  },
  hoursCell: {
    fontSize: 13,
    fontWeight: 700,
  },
  drilldown: {
    borderTop: '1px solid rgba(255,255,255,0.06)',
    padding: '8px 14px 12px',
  },
  rideRow: {
    display: 'grid',
    gridTemplateColumns: '1.5fr 1.2fr 0.8fr 0.8fr 0.7fr 0.7fr 0.8fr',
    padding: '7px 0',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
    gap: 4,
  },
  rideCell: {
    fontSize: 12,
    color: 'var(--text-muted)',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  rideCellBold: {
    fontSize: 12,
    color: 'var(--text)',
    fontWeight: 500,
  },
  drillHeader: {
    display: 'grid',
    gridTemplateColumns: '1.5fr 1.2fr 0.8fr 0.8fr 0.7fr 0.7fr 0.8fr',
    padding: '4px 0 6px',
    gap: 4,
  },
  drillHeaderCell: {
    fontSize: 10,
    fontWeight: 600,
    color: 'var(--text-muted)',
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
  },
}

function hoursColor(hours) {
  if (hours >= HOUR_TARGET) return 'var(--green)'
  if (hours >= 7) return 'var(--yellow)'
  return 'var(--red)'
}

function fmtDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function fmtWeek(weekStr) {
  // "2026-W15" → "W15"
  return weekStr.split('-')[1] || weekStr
}

function mean(arr) {
  const valid = arr.filter(v => v != null)
  return valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : null
}

function buildWeeks(rides) {
  const byWeek = {}
  for (const r of rides) {
    const w = r.week || 'unknown'
    if (!byWeek[w]) byWeek[w] = []
    byWeek[w].push(r)
  }

  return Object.entries(byWeek)
    .sort(([a], [b]) => b.localeCompare(a)) // newest first
    .map(([week, weekRides]) => {
      const totalMinutes = weekRides.reduce((s, r) => s + (r.duration_minutes || 0), 0)
      const z2Minutes = weekRides.reduce((s, r) => s + (r.zone_minutes?.z2 || 0), 0)
      const allZoneMinutes = weekRides.reduce((s, r) => {
        const zm = r.zone_minutes || {}
        return s + Object.values(zm).reduce((a, b) => a + b, 0)
      }, 0)

      return {
        week,
        rides: weekRides,
        hours: totalMinutes / 60,
        rideCount: weekRides.length,
        tss: weekRides.reduce((s, r) => s + (r.tss || 0), 0),
        kj: weekRides.reduce((s, r) => s + (r.kj || 0), 0),
        avgIF: mean(weekRides.map(r => r.intensity_factor)),
        avgEF: mean(weekRides.map(r => r.ef)),
        z2Pct: allZoneMinutes > 0 ? (z2Minutes / allZoneMinutes) * 100 : null,
      }
    })
}

function DrillDown({ rides }) {
  return (
    <div style={styles.drilldown}>
      <div style={styles.drillHeader}>
        {['Date', 'Type', 'Min', 'NP', 'IF', 'TSS', 'EF'].map(h => (
          <span key={h} style={styles.drillHeaderCell}>{h}</span>
        ))}
      </div>
      {[...rides].sort((a, b) => b.date.localeCompare(a.date)).map(r => (
        <div key={r.activity_id} style={styles.rideRow}>
          <span style={styles.rideCellBold}>{fmtDate(r.date)}</span>
          <span style={styles.rideCell}>{r.ride_type || '—'}</span>
          <span style={styles.rideCell}>{r.duration_minutes ?? '—'}</span>
          <span style={styles.rideCell}>{r.normalized_power ? `${r.normalized_power}W` : '—'}</span>
          <span style={styles.rideCell}>{r.intensity_factor?.toFixed(2) ?? '—'}</span>
          <span style={styles.rideCell}>{r.tss?.toFixed(0) ?? '—'}</span>
          <span style={styles.rideCell}>{r.ef?.toFixed(2) ?? '—'}</span>
        </div>
      ))}
    </div>
  )
}

export default function HistoryTable({ rides }) {
  const [expandedWeek, setExpandedWeek] = useState(null)

  if (!rides || rides.length === 0) {
    return (
      <div style={styles.empty}>
        No history yet — runs will appear here after your next ride analysis.
      </div>
    )
  }

  const weeks = buildWeeks(rides)

  return (
    <div>
      <div style={styles.colHeader}>
        {['Week', 'Hours', 'Rides', 'TSS', 'kJ', 'IF', 'EF', 'Z2%'].map(h => (
          <span key={h}>{h}</span>
        ))}
      </div>
      {weeks.map(w => {
        const expanded = expandedWeek === w.week
        return (
          <div key={w.week} style={styles.weekCard}>
            <div
              style={styles.weekRow}
              onClick={() => setExpandedWeek(expanded ? null : w.week)}
            >
              <span style={styles.weekLabel}>{fmtWeek(w.week)}</span>
              <span style={{ ...styles.hoursCell, color: hoursColor(w.hours) }}>
                {w.hours.toFixed(1)}h
              </span>
              <span style={styles.cell}>{w.rideCount}</span>
              <span style={styles.cell}>{w.tss.toFixed(0)}</span>
              <span style={styles.cell}>{Math.round(w.kj)}</span>
              <span style={styles.cell}>{w.avgIF?.toFixed(2) ?? '—'}</span>
              <span style={styles.cell}>{w.avgEF?.toFixed(2) ?? '—'}</span>
              <span style={styles.cell}>{w.z2Pct != null ? `${w.z2Pct.toFixed(0)}%` : '—'}</span>
            </div>
            {expanded && <DrillDown rides={w.rides} />}
          </div>
        )
      })}
    </div>
  )
}
