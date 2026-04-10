"""Parse streams CSV and FIT files into clean dataclasses."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class StreamPoint:
    time: int           # seconds from start
    watts: Optional[float]
    cadence: Optional[float]
    heartrate: Optional[float]
    distance: Optional[float]   # cumulative meters
    altitude: Optional[float]   # meters
    velocity: Optional[float]   # m/s
    temp: Optional[float]       # celsius
    torque: Optional[float]     # Nm
    balance: Optional[float]    # left power %
    respiration: Optional[float]  # breaths/min


@dataclass
class SessionMetrics:
    """Session-level metrics extracted from FIT files."""
    duration_seconds: Optional[int] = None
    avg_power: Optional[float] = None
    normalized_power: Optional[float] = None
    avg_hr: Optional[float] = None
    max_hr: Optional[float] = None
    avg_cadence: Optional[float] = None
    total_distance: Optional[float] = None  # meters
    total_calories: Optional[int] = None
    total_training_effect: Optional[float] = None
    total_anaerobic_training_effect: Optional[float] = None
    training_stress_score: Optional[float] = None
    intensity_factor: Optional[float] = None
    threshold_power: Optional[int] = None   # FTP from this source
    avg_temperature: Optional[float] = None
    max_temperature: Optional[float] = None
    source: str = ""  # "garmin" or "intervals"


@dataclass
class Ride:
    activity_id: str
    streams: List[StreamPoint] = field(default_factory=list)
    garmin_session: Optional[SessionMetrics] = None
    intervals_session: Optional[SessionMetrics] = None

    @property
    def duration_seconds(self) -> int:
        if self.streams:
            return self.streams[-1].time
        if self.garmin_session and self.garmin_session.duration_seconds:
            return self.garmin_session.duration_seconds
        return 0

    @property
    def watts_series(self) -> List[float]:
        return [p.watts for p in self.streams if p.watts is not None]

    @property
    def hr_series(self) -> List[float]:
        return [p.heartrate for p in self.streams if p.heartrate is not None]

    @property
    def cadence_series(self) -> List[float]:
        return [p.cadence for p in self.streams if p.cadence is not None]

    @property
    def respiration_series(self) -> List[float]:
        return [p.respiration for p in self.streams if p.respiration is not None]

    @property
    def balance_series(self) -> List[float]:
        return [p.balance for p in self.streams if p.balance is not None]


def _parse_float(value: str) -> Optional[float]:
    try:
        return float(value) if value.strip() else None
    except (ValueError, AttributeError):
        return None


def parse_streams_json(data: list) -> List[StreamPoint]:
    """Parse Intervals.icu streams JSON (columnar format) into StreamPoints.

    The API returns: [{"type": "time", "data": [0,1,2,...]}, {"type": "watts", "data": [...]}]
    """
    # Build a dict: channel_name -> list of values
    channels: dict = {}
    for channel in data:
        ctype = channel.get("type", "")
        channels[ctype] = channel.get("data", [])

    times = channels.get("time", [])
    if not times:
        return []

    def _col(name: str, idx: int) -> Optional[float]:
        col = channels.get(name, [])
        if idx >= len(col):
            return None
        v = col[idx]
        return float(v) if v is not None else None

    points = []
    for i, t in enumerate(times):
        if t is None:
            continue
        points.append(StreamPoint(
            time=int(t),
            watts=_col("watts", i),
            cadence=_col("cadence", i),
            heartrate=_col("heartrate", i),
            distance=_col("distance", i),
            altitude=_col("altitude", i),
            velocity=_col("velocity_smooth", i),
            temp=_col("temp", i),
            torque=_col("torque", i),
            balance=_col("left_right_balance", i),
            respiration=_col("respiration", i),
        ))
    return points


def parse_streams_csv(path: str) -> List[StreamPoint]:
    """Parse Intervals.icu streams CSV into a list of StreamPoints."""
    points = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("time", "").strip():
                continue
            points.append(StreamPoint(
                time=int(row["time"]),
                watts=_parse_float(row.get("watts", "")),
                cadence=_parse_float(row.get("cadence", "")),
                heartrate=_parse_float(row.get("heartrate", "")),
                distance=_parse_float(row.get("distance", "")),
                altitude=_parse_float(row.get("altitude", "")),
                velocity=_parse_float(row.get("velocity_smooth", "")),
                temp=_parse_float(row.get("temp", "")),
                torque=_parse_float(row.get("torque", "")),
                balance=_parse_float(row.get("left_right_balance", "")),
                respiration=_parse_float(row.get("respiration", "")),
            ))
    return points


def parse_fit_file(path: str) -> SessionMetrics:
    """Extract session-level metrics from a FIT file."""
    try:
        from fitparse import FitFile
    except ImportError:
        raise ImportError("fitparse is required: pip install fitparse")

    metrics = SessionMetrics()
    fit = FitFile(path)

    for record in fit.get_messages("session"):
        for data in record:
            name = data.name
            value = data.value
            if value is None:
                continue
            if name == "total_elapsed_time":
                metrics.duration_seconds = int(value)
            elif name == "avg_power":
                metrics.avg_power = float(value)
            elif name == "normalized_power":
                metrics.normalized_power = float(value)
            elif name == "avg_heart_rate":
                metrics.avg_hr = float(value)
            elif name == "max_heart_rate":
                metrics.max_hr = float(value)
            elif name == "avg_cadence":
                metrics.avg_cadence = float(value)
            elif name == "total_distance":
                metrics.total_distance = float(value)
            elif name == "total_calories":
                metrics.total_calories = int(value)
            elif name == "total_training_effect":
                metrics.total_training_effect = float(value)
            elif name == "total_anaerobic_training_effect":
                metrics.total_anaerobic_training_effect = float(value)
            elif name == "training_stress_score":
                metrics.training_stress_score = float(value)
            elif name == "intensity_factor":
                metrics.intensity_factor = float(value)
            elif name == "threshold_power":
                metrics.threshold_power = int(value)
            elif name == "avg_temperature":
                metrics.avg_temperature = float(value)
            elif name == "max_temperature":
                metrics.max_temperature = float(value)

    return metrics


def load_ride(
    activity_id: str,
    streams_path: Optional[str] = None,
    streams_json: Optional[list] = None,
    garmin_fit_path: Optional[str] = None,
    intervals_fit_path: Optional[str] = None,
) -> Ride:
    """Assemble a Ride from available data files or API data."""
    ride = Ride(activity_id=activity_id)

    if streams_json is not None:
        ride.streams = parse_streams_json(streams_json)
    elif streams_path and Path(streams_path).exists():
        ride.streams = parse_streams_csv(streams_path)

    if garmin_fit_path and Path(garmin_fit_path).exists():
        ride.garmin_session = parse_fit_file(garmin_fit_path)
        ride.garmin_session.source = "garmin"

    if intervals_fit_path and Path(intervals_fit_path).exists():
        ride.intervals_session = parse_fit_file(intervals_fit_path)
        ride.intervals_session.source = "intervals"

    return ride
