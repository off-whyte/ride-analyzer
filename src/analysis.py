"""Season-aware ride analysis engine."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import List, Optional

from .metrics import RideMetrics
from .ride_parser import Ride


@dataclass
class RideClassification:
    name: str           # e.g. "Endurance/Z2"
    description: str    # brief explanation


@dataclass
class FTPConflict:
    config_ftp: int
    garmin_ftp: Optional[int]
    intervals_ftp: Optional[int]
    warnings: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    season_phase: str
    ride_classification: RideClassification
    ftp_conflict: Optional[FTPConflict]
    observations: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    positives: List[str] = field(default_factory=list)


def get_season_phase(config: dict, date: Optional[datetime.date] = None) -> str:
    """Return the current season phase name based on config and date."""
    if date is None:
        date = datetime.date.today()
    phases = config.get("season", {}).get("phases", [])
    for phase in phases:
        start = datetime.date.fromisoformat(phase["start"])
        end = datetime.date.fromisoformat(phase["end"])
        if start <= date <= end:
            return phase["name"]
    return "off-season"


def classify_ride(m: RideMetrics) -> RideClassification:
    """Classify the ride type based on IF and zone distribution."""
    if m.intensity_factor is None or m.zones is None:
        return RideClassification("Unknown", "Insufficient data to classify")

    IF = m.intensity_factor
    zones = m.zones.as_percents()
    z5z6_pct = zones["z5"] + zones["z6"]
    vi = m.variability_index or 1.0

    if IF < 0.6:
        return RideClassification("Recovery", "Easy spin, well below aerobic threshold")

    if IF < 0.75:
        return RideClassification("Endurance/Z2", "Aerobic endurance ride, primary base building")

    if 0.75 <= IF < 0.88:
        return RideClassification("Tempo/Sweet Spot", "Moderate-high intensity, significant Z3-Z4 time")

    if 0.88 <= IF < 1.0 and z5z6_pct < 15:
        return RideClassification("Threshold", "High intensity near FTP, structured threshold work")

    if z5z6_pct >= 15:
        return RideClassification("VO2max/Anaerobic", "Significant time above threshold, high-intensity intervals")

    if vi > 1.15:
        return RideClassification("Race/Group Ride", "Highly variable power, mixed intensity zones")

    return RideClassification("Mixed Intensity", f"IF={IF:.2f}, varied effort")


def check_ftp_conflicts(config: dict, ride: Ride) -> Optional[FTPConflict]:
    config_ftp = config["athlete"]["ftp"]
    garmin_ftp = ride.garmin_session.threshold_power if ride.garmin_session else None
    intervals_ftp = ride.intervals_session.threshold_power if ride.intervals_session else None

    warnings = []
    threshold = 15  # warn if >15W off

    if garmin_ftp and abs(garmin_ftp - config_ftp) > threshold:
        warnings.append(
            f"Garmin FTP ({garmin_ftp}W) differs from config FTP ({config_ftp}W) by "
            f"{abs(garmin_ftp - config_ftp)}W — using config value"
        )
    if intervals_ftp and abs(intervals_ftp - config_ftp) > threshold:
        warnings.append(
            f"Intervals.icu FTP ({intervals_ftp}W) differs from config FTP ({config_ftp}W) by "
            f"{abs(intervals_ftp - config_ftp)}W — using config value"
        )

    if not warnings and not garmin_ftp and not intervals_ftp:
        return None

    return FTPConflict(
        config_ftp=config_ftp,
        garmin_ftp=garmin_ftp,
        intervals_ftp=intervals_ftp,
        warnings=warnings,
    )


def _fmt_time(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def analyze(ride: Ride, m: RideMetrics, config: dict, date: Optional[datetime.date] = None) -> AnalysisResult:
    """Run season-aware analysis and generate observations."""
    phase = get_season_phase(config, date)
    classification = classify_ride(m)
    ftp_conflict = check_ftp_conflicts(config, ride)

    observations = []
    flags = []
    positives = []

    zones = m.zones.as_percents() if m.zones else {}
    z3plus = zones.get("z3", 0) + zones.get("z4", 0) + zones.get("z5", 0) + zones.get("z6", 0)
    z3plus_minutes = z3plus / 100 * m.duration_seconds / 60 if m.duration_seconds else 0

    # --- Base phase analysis ---
    if phase == "base":
        if classification.name == "Endurance/Z2":
            positives.append("Good Z2 endurance ride — exactly what base phase calls for.")

        if z3plus_minutes > 10 and classification.name not in ("Tempo/Sweet Spot", "Threshold"):
            flags.append(
                f"You spent {z3plus_minutes:.0f} minutes above Z2. "
                f"In base, aim for under 10 minutes of Z3+ on endurance rides unless it's a planned tempo day."
            )
        elif z3plus_minutes <= 5 and classification.name == "Endurance/Z2":
            positives.append(f"Excellent zone discipline — only {z3plus_minutes:.0f} min above Z2.")

        if m.hr_drift_pct is not None:
            if m.hr_drift_pct < 5:
                positives.append(
                    f"HR drift: {m.hr_drift_pct:.1f}% over the ride — under 5% is solid for base building."
                )
            else:
                flags.append(
                    f"HR drift: {m.hr_drift_pct:.1f}% — above 5% suggests you may be approaching your aerobic ceiling "
                    f"at this intensity. Try easing off power slightly on long Z2 rides."
                )

        if m.cardiac_decoupling_pct is not None:
            if m.cardiac_decoupling_pct < 5:
                positives.append(
                    f"Cardiac decoupling: {m.cardiac_decoupling_pct:.1f}% — aerobic system is holding well."
                )
            else:
                flags.append(
                    f"Cardiac decoupling: {m.cardiac_decoupling_pct:.1f}% (>5% = cardiovascular drift). "
                    f"Good sign that base work is pushing your limits."
                )

        if m.respiration_trend:
            start_resp, end_resp = m.respiration_trend
            resp_rise = end_resp - start_resp
            observations.append(
                f"Respiration trend: {start_resp} → {end_resp} breaths/min "
                f"({'rising' if resp_rise > 2 else 'stable'} through ride)."
            )
            if resp_rise > 5:
                flags.append(
                    "Significant respiration rate rise during the ride. "
                    "Track this week over week — sustained rise at constant power signals aerobic drift."
                )

        if m.avg_balance is not None:
            if abs(m.avg_balance - 50) > 3:
                dominant = "left" if m.avg_balance > 50 else "right"
                flags.append(
                    f"L/R balance: {m.avg_balance:.1f}% left — consistently over 53/47 toward {dominant}. "
                    f"Worth monitoring for asymmetry."
                )
            else:
                observations.append(f"L/R balance: {m.avg_balance:.1f}% left — well balanced.")

    # --- Build 1 phase analysis ---
    elif phase == "build1":
        if m.intensity_factor and m.intensity_factor >= 0.88:
            observations.append("Threshold intensity work — track interval quality and HR recovery between efforts.")
        if m.variability_index and m.variability_index > 1.1:
            observations.append(
                f"Variability index: {m.variability_index:.2f} — somewhat variable effort. "
                f"For threshold work, aim for VI closer to 1.05."
            )

    # --- Build 2 / Peak phase analysis ---
    elif phase in ("build2", "peak"):
        if m.peak_powers:
            pp = m.peak_powers
            if pp.p30s:
                observations.append(f"Peak 30s power: {pp.p30s:.0f}W ({pp.p30s/m.ftp_used*100:.0f}% FTP)")
            if pp.p1min:
                observations.append(f"Peak 1min power: {pp.p1min:.0f}W ({pp.p1min/m.ftp_used*100:.0f}% FTP)")
            if pp.p5min:
                observations.append(f"Peak 5min power: {pp.p5min:.0f}W ({pp.p5min/m.ftp_used*100:.0f}% FTP)")

    # --- Universal observations ---
    if m.ef_windows:
        ef_vals = [ef for _, ef in m.ef_windows]
        ef_min, ef_max = min(ef_vals), max(ef_vals)
        observations.append(f"EF range across 10-min windows: {ef_min:.2f} – {ef_max:.2f} W/bpm")

    return AnalysisResult(
        season_phase=phase,
        ride_classification=classification,
        ftp_conflict=ftp_conflict,
        observations=observations,
        flags=flags,
        positives=positives,
    )
