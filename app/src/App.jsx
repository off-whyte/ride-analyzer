import { useState, useEffect } from 'react'
import MetricCard from './components/MetricCard'
import NextWorkout from './components/NextWorkout'
import ZoneBar from './components/ZoneBar'
import EfSparkline from './components/EfSparkline'
import WeeklyProgress from './components/WeeklyProgress'

const styles = {
  app: {
    maxWidth: 480,
    margin: '0 auto',
    padding: '16px 16px 32px',
    minHeight: '100vh',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 20,
    paddingTop: 'env(safe-area-inset-top)',
  },
  title: {
    fontSize: 13,
    fontWeight: 600,
    color: 'var(--text-muted)',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
  },
  badge: {
    background: 'var(--green-dim)',
    color: 'var(--green)',
    padding: '4px 10px',
    borderRadius: 20,
    fontSize: 13,
    fontWeight: 600,
  },
  rideMeta: {
    fontSize: 22,
    fontWeight: 700,
    marginBottom: 4,
  },
  rideDate: {
    fontSize: 14,
    color: 'var(--text-muted)',
    marginBottom: 20,
  },
  metricsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 12,
    marginBottom: 20,
  },
  section: {
    background: 'var(--surface)',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--text-muted)',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    marginBottom: 10,
  },
  hrDriftRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  hrDriftLabel: {
    fontSize: 14,
    color: 'var(--text-muted)',
  },
  hrDriftValue: {
    fontSize: 18,
    fontWeight: 700,
  },
  decouplingRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 10,
  },
  positives: {
    marginTop: 12,
  },
  positive: {
    fontSize: 13,
    color: 'var(--green)',
    paddingLeft: 14,
    position: 'relative',
    marginBottom: 4,
  },
  flag: {
    fontSize: 13,
    color: 'var(--yellow)',
    paddingLeft: 14,
    position: 'relative',
    marginBottom: 4,
  },
  timestamp: {
    fontSize: 12,
    color: 'var(--text-muted)',
    textAlign: 'center',
    marginTop: 16,
  },
  triggerBtn: {
    background: 'var(--green)',
    color: '#000',
    border: 'none',
    borderRadius: 8,
    padding: '10px 18px',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
  },
  triggerBtnSmall: {
    background: 'transparent',
    color: 'var(--text-muted)',
    border: '1px solid var(--surface)',
    borderRadius: 6,
    padding: '4px 10px',
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
  },
  loadingState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '60vh',
    gap: 12,
    color: 'var(--text-muted)',
  },
  errorState: {
    background: 'var(--surface)',
    borderRadius: 12,
    padding: 20,
    margin: '40px 16px',
    textAlign: 'center',
  },
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function hrDriftColor(pct) {
  if (pct == null) return 'var(--text-muted)'
  if (pct < 5) return 'var(--green)'
  if (pct < 8) return 'var(--yellow)'
  return 'var(--red)'
}

const REPO = 'off-whyte/ride-analyzer'
const WORKFLOW = 'analyze-ride.yml'

async function triggerWorkflow(token) {
  const res = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ref: 'main' }),
    }
  )
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`GitHub API ${res.status}: ${text}`)
  }
}

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [triggered, setTriggered] = useState(false)

  useEffect(() => {
    fetch('data/latest-analysis.json')
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(json => { setData(json); setLoading(false) })
      .catch(err => { setError(err.message); setLoading(false) })
  }, [])

  async function handleTrigger() {
    let token = localStorage.getItem('gh_token')
    if (!token) {
      token = window.prompt(
        'Enter a GitHub personal access token with Actions (workflow) write permission.\n\nThis is saved to localStorage on this device only.'
      )
      if (!token) return
      localStorage.setItem('gh_token', token.trim())
      token = token.trim()
    }
    setTriggering(true)
    try {
      await triggerWorkflow(token)
      setTriggered(true)
    } catch (e) {
      if (e.message.includes('401') || e.message.includes('403')) {
        localStorage.removeItem('gh_token')
      }
      alert(`Failed to trigger workflow:\n${e.message}`)
    } finally {
      setTriggering(false)
    }
  }

  if (loading) {
    return (
      <div style={styles.app}>
        <div style={styles.loadingState}>
          <div style={{ fontSize: 32 }}>🚴</div>
          <div>Loading analysis…</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={styles.app}>
        <div style={styles.errorState}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>⚠️</div>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>No analysis found</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
            Run the analyzer to pull your latest ride from Intervals.icu.
          </div>
          {triggered ? (
            <div style={{ fontSize: 13, color: 'var(--green)' }}>
              Analysis running… check back in a minute.
            </div>
          ) : (
            <button onClick={handleTrigger} disabled={triggering} style={styles.triggerBtn}>
              {triggering ? 'Starting…' : 'Analyze Latest Ride'}
            </button>
          )}
        </div>
      </div>
    )
  }

  const { summary, aerobic_indicators, zone_distribution, weekly_context, season, next_workout, analysis } = data

  const driftPct = aerobic_indicators?.hr_drift_pct
  const decouplingPct = aerobic_indicators?.cardiac_decoupling_pct

  return (
    <div style={styles.app}>
      {/* Header */}
      <div style={styles.header}>
        <span style={styles.title}>Ride Analyzer</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {triggered ? (
            <span style={{ fontSize: 12, color: 'var(--green)' }}>Running…</span>
          ) : (
            <button onClick={handleTrigger} disabled={triggering} style={styles.triggerBtnSmall}>
              {triggering ? '…' : 'Run'}
            </button>
          )}
          <span style={styles.badge}>{data.ride_type}</span>
        </div>
      </div>

      {/* Ride title */}
      <div style={styles.rideMeta}>
        {formatDate(data.activity_date)}
      </div>
      <div style={styles.rideDate}>
        {data.duration_minutes} min
        {summary?.distance_km ? ` · ${summary.distance_km} km` : ''}
        {season?.current_phase ? ` · ${season.current_phase.charAt(0).toUpperCase() + season.current_phase.slice(1)} phase` : ''}
      </div>

      {/* Next workout — most prominent */}
      {next_workout && <NextWorkout workout={next_workout} />}

      {/* Big 4 metrics */}
      <div style={styles.metricsGrid}>
        <MetricCard label="NP" value={summary?.normalized_power} unit="W" />
        <MetricCard label="IF" value={summary?.intensity_factor?.toFixed(2)} unit="" />
        <MetricCard label="TSS" value={summary?.tss} unit="" />
        <MetricCard label="Duration" value={data.duration_minutes} unit="min" />
      </div>

      {/* HR drift + cardiac decoupling */}
      <div style={styles.section}>
        <div style={styles.sectionLabel}>Aerobic Indicators</div>
        <div style={styles.hrDriftRow}>
          <span style={styles.hrDriftLabel}>HR Drift</span>
          <span style={{ ...styles.hrDriftValue, color: hrDriftColor(driftPct) }}>
            {driftPct != null ? `${driftPct > 0 ? '+' : ''}${driftPct.toFixed(1)}%` : '—'}
          </span>
        </div>
        <div style={styles.decouplingRow}>
          <span style={styles.hrDriftLabel}>Cardiac Decoupling</span>
          <span style={{ ...styles.hrDriftValue, color: hrDriftColor(decouplingPct), fontSize: 16 }}>
            {decouplingPct != null ? `${decouplingPct.toFixed(1)}%` : '—'}
          </span>
        </div>

        {/* EF sparkline */}
        {aerobic_indicators?.ef_trend?.length > 0 && (
          <EfSparkline data={aerobic_indicators.ef_trend} />
        )}

        {/* Positives and flags */}
        {analysis && (analysis.positives?.length > 0 || analysis.flags?.length > 0) && (
          <div style={styles.positives}>
            {analysis.positives?.map((p, i) => (
              <div key={i} style={styles.positive}>✓ {p}</div>
            ))}
            {analysis.flags?.map((f, i) => (
              <div key={i} style={styles.flag}>⚠ {f}</div>
            ))}
          </div>
        )}
      </div>

      {/* Zone distribution */}
      {zone_distribution && (
        <div style={styles.section}>
          <div style={styles.sectionLabel}>Zone Distribution</div>
          <ZoneBar zones={zone_distribution} />
        </div>
      )}

      {/* Weekly progress */}
      {weekly_context && (
        <div style={styles.section}>
          <div style={styles.sectionLabel}>This Week</div>
          <WeeklyProgress context={weekly_context} />
        </div>
      )}

      {/* Season */}
      {season?.target_event && (
        <div style={styles.section}>
          <div style={styles.sectionLabel}>Season</div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 14 }}>{season.target_event}</span>
            {season.weeks_to_target != null && (
              <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>
                {season.weeks_to_target}w out
              </span>
            )}
          </div>
        </div>
      )}

      {/* Timestamp */}
      <div style={styles.timestamp}>
        Updated {new Date(data.generated_at).toLocaleString()}
      </div>
    </div>
  )
}
