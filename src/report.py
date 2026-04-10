"""Format ride analysis as markdown output."""

from __future__ import annotations

import datetime
from typing import Optional

from .metrics import RideMetrics
from .analysis import AnalysisResult
from .workout_suggest import WorkoutSuggestion


def _fmt_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m {s:02d}s"


def _zone_bar(pct: float, width: int = 20) -> str:
    filled = int(round(pct / 100 * width))
    return "█" * filled + "░" * (width - filled)


def render_report(
    activity_id: str,
    m: RideMetrics,
    result: AnalysisResult,
    suggestion: Optional[WorkoutSuggestion] = None,
    date: Optional[datetime.date] = None,
) -> str:
    lines = []
    date_str = date.isoformat() if date else datetime.date.today().isoformat()

    lines.append(f"# Ride Analysis — {date_str}")
    lines.append(f"Activity: {activity_id} | Phase: **{result.season_phase.upper()}** | "
                 f"Classification: **{result.ride_classification.name}**")
    lines.append("")

    # FTP conflicts
    if result.ftp_conflict and result.ftp_conflict.warnings:
        lines.append("## ⚠ FTP Discrepancies")
        for w in result.ftp_conflict.warnings:
            lines.append(f"- {w}")
        lines.append(f"\n_Using FTP = {m.ftp_used}W for all calculations._")
        lines.append("")

    # Key metrics
    lines.append("## Ride Summary")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Duration | {_fmt_duration(m.duration_seconds)} |")
    if m.avg_power is not None:
        lines.append(f"| Avg Power | {m.avg_power:.0f}W |")
    if m.normalized_power is not None:
        lines.append(f"| Normalized Power | {m.normalized_power:.0f}W |")
    if m.intensity_factor is not None:
        lines.append(f"| Intensity Factor | {m.intensity_factor:.2f} |")
    if m.tss is not None:
        lines.append(f"| TSS | {m.tss:.1f} |")
    if m.variability_index is not None:
        lines.append(f"| Variability Index | {m.variability_index:.2f} |")
    if m.avg_hr is not None:
        lines.append(f"| Avg HR | {m.avg_hr:.0f} bpm |")
    if m.max_hr is not None:
        lines.append(f"| Max HR | {m.max_hr:.0f} bpm |")
    if m.efficiency_factor is not None:
        lines.append(f"| Efficiency Factor | {m.efficiency_factor:.3f} W/bpm |")
    if m.avg_cadence is not None:
        lines.append(f"| Avg Cadence | {m.avg_cadence:.0f} rpm |")
    if m.avg_respiration is not None:
        lines.append(f"| Avg Respiration | {m.avg_respiration:.1f} breaths/min |")
    if m.avg_balance is not None:
        lines.append(f"| L/R Balance | {m.avg_balance:.1f}% / {100 - m.avg_balance:.1f}% |")
    lines.append("")

    # Zone distribution
    if m.zones:
        pcts = m.zones.as_percents()
        lines.append("## Zone Distribution")
        zone_labels = {
            "z1": f"Z1 <55% FTP (<{int(m.ftp_used*0.55)}W)",
            "z2": f"Z2 55-75% ({int(m.ftp_used*0.55)}-{int(m.ftp_used*0.75)}W)",
            "z3": f"Z3 75-90% ({int(m.ftp_used*0.75)}-{int(m.ftp_used*0.90)}W)",
            "z4": f"Z4 90-105% ({int(m.ftp_used*0.90)}-{int(m.ftp_used*1.05)}W)",
            "z5": f"Z5 105-120% ({int(m.ftp_used*1.05)}-{int(m.ftp_used*1.20)}W)",
            "z6": f"Z6 >120% (>{int(m.ftp_used*1.20)}W)",
        }
        for z, label in zone_labels.items():
            pct = pcts[z]
            secs = getattr(m.zones, f"{z}_seconds")
            if pct > 0 or z in ("z1", "z2"):
                bar = _zone_bar(pct)
                lines.append(f"`{bar}` {pct:4.1f}% ({_fmt_duration(int(secs))})  {label}")
        lines.append("")

    # Drift and aerobic indicators
    aerobic_lines = []
    if m.hr_drift_pct is not None:
        aerobic_lines.append(f"- **HR drift:** {m.hr_drift_pct:+.1f}% (first→second half)")
    if m.power_drift_pct is not None:
        aerobic_lines.append(f"- **Power drift:** {m.power_drift_pct:+.1f}% (first→second half)")
    if m.cardiac_decoupling_pct is not None:
        aerobic_lines.append(f"- **Cardiac decoupling:** {m.cardiac_decoupling_pct:.1f}% EF degradation")
    if m.respiration_trend:
        aerobic_lines.append(
            f"- **Respiration trend:** {m.respiration_trend[0]} → {m.respiration_trend[1]} breaths/min"
        )
    if m.ef_windows:
        ef_vals = [ef for _, ef in m.ef_windows]
        aerobic_lines.append(
            f"- **EF windows (10-min):** {min(ef_vals):.2f} – {max(ef_vals):.2f} W/bpm"
        )

    if aerobic_lines:
        lines.append("## Aerobic Indicators")
        lines.extend(aerobic_lines)
        lines.append("")

    # Peak powers
    if m.peak_powers:
        pp = m.peak_powers
        peak_lines = []
        if pp.p10s:
            peak_lines.append(f"| 10 sec | {pp.p10s:.0f}W | {pp.p10s/m.ftp_used*100:.0f}% FTP |")
        if pp.p30s:
            peak_lines.append(f"| 30 sec | {pp.p30s:.0f}W | {pp.p30s/m.ftp_used*100:.0f}% FTP |")
        if pp.p1min:
            peak_lines.append(f"| 1 min  | {pp.p1min:.0f}W | {pp.p1min/m.ftp_used*100:.0f}% FTP |")
        if pp.p2min:
            peak_lines.append(f"| 2 min  | {pp.p2min:.0f}W | {pp.p2min/m.ftp_used*100:.0f}% FTP |")
        if pp.p5min:
            peak_lines.append(f"| 5 min  | {pp.p5min:.0f}W | {pp.p5min/m.ftp_used*100:.0f}% FTP |")
        if pp.p20min:
            peak_lines.append(f"| 20 min | {pp.p20min:.0f}W | {pp.p20min/m.ftp_used*100:.0f}% FTP |")
        if peak_lines:
            lines.append("## Peak Powers")
            lines.append("| Duration | Power | % FTP |")
            lines.append("|----------|-------|-------|")
            lines.extend(peak_lines)
            lines.append("")

    # Analysis
    if result.positives or result.flags or result.observations:
        lines.append("## Analysis")
        for p in result.positives:
            lines.append(f"✓ {p}")
        for f in result.flags:
            lines.append(f"⚠ {f}")
        for o in result.observations:
            lines.append(f"→ {o}")
        lines.append("")

    # Next workout
    if suggestion:
        lines.append("## Next Workout Suggestion")
        lines.append(f"**{suggestion.title}**")
        if suggestion.duration_minutes > 0:
            lines.append(f"Duration: {suggestion.duration_minutes} min | Intensity: {suggestion.intensity}")
        lines.append("")
        lines.append(suggestion.description)
        lines.append("")
        lines.append(f"_Reason: {suggestion.reasoning}_")
        lines.append("")

    return "\n".join(lines)
