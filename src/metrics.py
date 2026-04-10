"""Compute training metrics from ride data."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .ride_parser import Ride


@dataclass
class ZoneDistribution:
    z1_seconds: float = 0.0
    z2_seconds: float = 0.0
    z3_seconds: float = 0.0
    z4_seconds: float = 0.0
    z5_seconds: float = 0.0
    z6_seconds: float = 0.0

    def total(self) -> float:
        return (self.z1_seconds + self.z2_seconds + self.z3_seconds +
                self.z4_seconds + self.z5_seconds + self.z6_seconds)

    def as_percents(self) -> Dict[str, float]:
        total = self.total()
        if total == 0:
            return {z: 0.0 for z in ["z1", "z2", "z3", "z4", "z5", "z6"]}
        return {
            "z1": self.z1_seconds / total * 100,
            "z2": self.z2_seconds / total * 100,
            "z3": self.z3_seconds / total * 100,
            "z4": self.z4_seconds / total * 100,
            "z5": self.z5_seconds / total * 100,
            "z6": self.z6_seconds / total * 100,
        }


@dataclass
class PeakPowers:
    p10s: Optional[float] = None
    p30s: Optional[float] = None
    p1min: Optional[float] = None
    p2min: Optional[float] = None
    p5min: Optional[float] = None
    p20min: Optional[float] = None


@dataclass
class RideMetrics:
    duration_seconds: int = 0
    avg_power: Optional[float] = None
    normalized_power: Optional[float] = None
    intensity_factor: Optional[float] = None
    tss: Optional[float] = None
    avg_hr: Optional[float] = None
    max_hr: Optional[float] = None
    avg_cadence: Optional[float] = None
    avg_respiration: Optional[float] = None
    avg_balance: Optional[float] = None
    variability_index: Optional[float] = None  # NP / avg_power
    efficiency_factor: Optional[float] = None  # NP / avg_hr
    zones: Optional[ZoneDistribution] = None
    hr_drift_pct: Optional[float] = None        # HR first half vs second half
    power_drift_pct: Optional[float] = None
    cardiac_decoupling_pct: Optional[float] = None  # EF second/first half
    ef_windows: List[Tuple[int, float]] = field(default_factory=list)  # (minute, EF)
    respiration_trend: Optional[Tuple[float, float]] = None  # (start_avg, end_avg)
    peak_powers: Optional[PeakPowers] = None
    ftp_used: int = 250


def normalized_power(watts: List[float]) -> float:
    """30-second rolling average, then 4th-power mean, then 4th root."""
    if len(watts) < 30:
        return sum(watts) / len(watts) if watts else 0.0

    window = 30
    rolling = []
    for i in range(window - 1, len(watts)):
        avg = sum(watts[i - window + 1:i + 1]) / window
        rolling.append(avg)

    mean_4th = sum(v ** 4 for v in rolling) / len(rolling)
    return mean_4th ** 0.25


def zone_for_power(watts: float, ftp: int) -> str:
    pct = watts / ftp * 100
    if pct < 55:
        return "z1"
    elif pct < 75:
        return "z2"
    elif pct < 90:
        return "z3"
    elif pct < 105:
        return "z4"
    elif pct < 120:
        return "z5"
    else:
        return "z6"


def zone_distribution(watts: List[float], ftp: int) -> ZoneDistribution:
    """Each element = 1 second, count time in each zone."""
    dist = ZoneDistribution()
    for w in watts:
        z = zone_for_power(w, ftp)
        setattr(dist, f"{z}_seconds", getattr(dist, f"{z}_seconds") + 1.0)
    return dist


def peak_power_for_duration(watts: List[float], duration_seconds: int) -> Optional[float]:
    """Best average power over a sliding window of duration_seconds."""
    if len(watts) < duration_seconds:
        return None
    best = 0.0
    for i in range(len(watts) - duration_seconds + 1):
        window_avg = sum(watts[i:i + duration_seconds]) / duration_seconds
        if window_avg > best:
            best = window_avg
    return best


def compute_peak_powers(watts: List[float]) -> PeakPowers:
    return PeakPowers(
        p10s=peak_power_for_duration(watts, 10),
        p30s=peak_power_for_duration(watts, 30),
        p1min=peak_power_for_duration(watts, 60),
        p2min=peak_power_for_duration(watts, 120),
        p5min=peak_power_for_duration(watts, 300),
        p20min=peak_power_for_duration(watts, 1200),
    )


def _avg(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _drift_pct(first: float, second: float) -> float:
    """Percentage increase from first to second."""
    if first == 0:
        return 0.0
    return (second - first) / first * 100


def compute_ef_windows(watts: List[float], hr: List[float], window_minutes: int = 10) -> List[Tuple[int, float]]:
    """Compute efficiency factor (NP/avg_HR) for each N-minute window."""
    window_sec = window_minutes * 60
    results = []
    if len(watts) < window_sec or len(hr) < window_sec:
        return results

    n = min(len(watts), len(hr))
    for start in range(0, n - window_sec + 1, window_sec):
        end = start + window_sec
        w_slice = watts[start:end]
        hr_slice = hr[start:end]
        np_val = normalized_power(w_slice)
        avg_hr_val = _avg(hr_slice)
        if avg_hr_val and avg_hr_val > 0:
            ef = np_val / avg_hr_val
            minute = start // 60
            results.append((minute, round(ef, 3)))
    return results


def compute_metrics(ride: Ride, ftp: int) -> RideMetrics:
    """Compute all metrics from a Ride object."""
    m = RideMetrics(ftp_used=ftp)
    m.duration_seconds = ride.duration_seconds

    watts = ride.watts_series
    hr = ride.hr_series
    cadence = ride.cadence_series
    resp = ride.respiration_series
    balance = ride.balance_series

    if watts:
        m.avg_power = _avg(watts)
        m.normalized_power = normalized_power(watts)
        m.zones = zone_distribution(watts, ftp)
        m.peak_powers = compute_peak_powers(watts)

        if m.normalized_power and m.avg_power and m.avg_power > 0:
            m.variability_index = round(m.normalized_power / m.avg_power, 3)

        if m.normalized_power:
            m.intensity_factor = round(m.normalized_power / ftp, 3)
            duration_hours = m.duration_seconds / 3600
            m.tss = round((m.duration_seconds * m.normalized_power * m.intensity_factor) / (ftp * 3600) * 100, 1)

        # Power drift: first half vs second half
        mid = len(watts) // 2
        first_half_power = _avg(watts[:mid])
        second_half_power = _avg(watts[mid:])
        if first_half_power and second_half_power:
            m.power_drift_pct = round(_drift_pct(first_half_power, second_half_power), 1)

    if hr:
        m.avg_hr = round(_avg(hr), 1)
        m.max_hr = max(hr)

        # HR drift: first half vs second half
        mid = len(hr) // 2
        first_half_hr = _avg(hr[:mid])
        second_half_hr = _avg(hr[mid:])
        if first_half_hr and second_half_hr:
            m.hr_drift_pct = round(_drift_pct(first_half_hr, second_half_hr), 1)

    if watts and hr:
        m.efficiency_factor = round(m.normalized_power / m.avg_hr, 3) if (m.normalized_power and m.avg_hr) else None
        m.ef_windows = compute_ef_windows(watts, hr)

        # Cardiac decoupling: EF in second half vs first half of steady-state
        n = min(len(watts), len(hr))
        mid = n // 2
        np_first = normalized_power(watts[:mid])
        np_second = normalized_power(watts[mid:])
        hr_first = _avg(hr[:mid])
        hr_second = _avg(hr[mid:])
        if hr_first and hr_second and hr_first > 0 and hr_second > 0:
            ef_first = np_first / hr_first
            ef_second = np_second / hr_second
            if ef_first > 0:
                # Decoupling = how much EF degraded (positive = degraded)
                m.cardiac_decoupling_pct = round(_drift_pct(ef_first, ef_second) * -1, 1)

    if cadence:
        m.avg_cadence = round(_avg(cadence), 1)

    if resp:
        m.avg_respiration = round(_avg(resp), 1)
        # Trend: avg of first quarter vs last quarter
        q = max(1, len(resp) // 4)
        start_avg = _avg(resp[:q])
        end_avg = _avg(resp[-q:])
        if start_avg and end_avg:
            m.respiration_trend = (round(start_avg, 1), round(end_avg, 1))

    if balance:
        m.avg_balance = round(_avg(balance), 1)

    return m
