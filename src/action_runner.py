"""Orchestrator: fetch latest ride, run analysis, write data/latest-analysis.json."""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

import yaml

# Allow running as a script from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.intervals_client import IntervalsClient, build_recent_load_from_activities
from src.ride_parser import load_ride
from src.metrics import compute_metrics
from src.analysis import analyze, get_season_phase, classify_ride
from src.workout_suggest import suggest_next_workout


def iso_week(date_str: str) -> str:
    d = datetime.date.fromisoformat(date_str)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def append_history(activity: dict, metrics, analysis_result, out_path: Path) -> None:
    """Append a lean record to ride-history.json, deduplicating on activity_id."""
    activity_id = activity.get("id", "")
    date_str = activity.get("start_date_local", "")[:10]

    record = {
        "activity_id": activity_id,
        "date": date_str,
        "week": iso_week(date_str) if date_str else "",
        "ride_type": analysis_result.ride_classification.name.lower(),
        "duration_minutes": round(metrics.duration_seconds / 60, 1),
        "avg_power": round(metrics.avg_power) if metrics.avg_power else None,
        "normalized_power": round(metrics.normalized_power) if metrics.normalized_power else None,
        "intensity_factor": metrics.intensity_factor,
        "tss": metrics.tss,
        "kj": metrics.kj,
        "avg_hr": metrics.avg_hr,
        "ef": round(metrics.efficiency_factor, 3) if metrics.efficiency_factor else None,
        "hr_drift_pct": metrics.hr_drift_pct,
        "zone_minutes": {
            "z1": round(metrics.zones.z1_seconds / 60, 1),
            "z2": round(metrics.zones.z2_seconds / 60, 1),
            "z3": round(metrics.zones.z3_seconds / 60, 1),
            "z4": round(metrics.zones.z4_seconds / 60, 1),
            "z5": round(metrics.zones.z5_seconds / 60, 1),
            "z6": round(metrics.zones.z6_seconds / 60, 1),
        } if metrics.zones else {},
    }

    history = []
    if out_path.exists():
        with open(out_path) as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = []

    # Deduplicate on activity_id
    history = [r for r in history if r.get("activity_id") != activity_id]
    history.append(record)
    history.sort(key=lambda r: r.get("date", ""))

    with open(out_path, "w") as f:
        json.dump(history, f, indent=2)


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def build_output(activity: dict, ride, metrics, analysis_result, suggestion, recent_activities: list, config: dict) -> dict:
    ftp = config["athlete"]["ftp"]
    today = datetime.date.today()

    # Weekly context
    weekly_target = config.get("training", {}).get("weekly_hour_target", 10)
    from src.intervals_client import build_recent_load_from_activities
    load = build_recent_load_from_activities(recent_activities)
    days_remaining = 7 - today.weekday()  # days left including today

    # EF trend (minute, ef)
    ef_trend = [{"minute": m, "ef": ef} for m, ef in metrics.ef_windows]

    # Respiration trend (minute, resp) — sample from ride every 10 min
    resp_trend = []
    if ride.respiration_series:
        window = 600  # 10 min in seconds
        resp_all = ride.respiration_series
        # Use windows aligned to ef_windows for consistency
        for i, (minute, _) in enumerate(metrics.ef_windows):
            start = minute * 60
            end = start + window
            # Sample the respiration series at this window
            resp_window = [
                p.respiration
                for p in ride.streams
                if start <= p.time < end and p.respiration is not None
            ]
            if resp_window:
                avg_resp = sum(resp_window) / len(resp_window)
                resp_trend.append({"minute": minute, "resp": round(avg_resp, 1)})

    # Zone distribution in minutes
    zones = metrics.zones
    zone_dist = {}
    if zones:
        zone_dist = {
            "z1_minutes": round(zones.z1_seconds / 60, 1),
            "z2_minutes": round(zones.z2_seconds / 60, 1),
            "z3_minutes": round(zones.z3_seconds / 60, 1),
            "z4_minutes": round(zones.z4_seconds / 60, 1),
            "z5_minutes": round(zones.z5_seconds / 60, 1),
            "z6_minutes": round(zones.z6_seconds / 60, 1),
        }

    # Season info
    season_cfg = config.get("season", {})
    target_date_str = season_cfg.get("target_date", "")
    weeks_to_target = None
    if target_date_str:
        target = datetime.date.fromisoformat(target_date_str)
        delta = target - today
        weeks_to_target = max(0, delta.days // 7)

    # Left/right balance
    lr_balance = None
    if metrics.avg_balance is not None:
        lr_balance = {
            "avg_left_pct": round(metrics.avg_balance, 1),
            "flag": abs(metrics.avg_balance - 50) > 3,
        }

    # Activity date
    activity_date = activity.get("start_date_local", "")[:19]

    return {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "activity_id": activity.get("id", ""),
        "activity_date": activity_date,
        "ride_type": analysis_result.ride_classification.name,
        "duration_minutes": round(metrics.duration_seconds / 60, 1),
        "summary": {
            "avg_power": round(metrics.avg_power) if metrics.avg_power else None,
            "normalized_power": round(metrics.normalized_power) if metrics.normalized_power else None,
            "intensity_factor": metrics.intensity_factor,
            "tss": metrics.tss,
            "avg_hr": metrics.avg_hr,
            "max_hr": metrics.max_hr,
            "avg_cadence": metrics.avg_cadence,
            "avg_respiration": metrics.avg_respiration,
            "distance_km": round(activity.get("distance", 0) / 1000, 1) if activity.get("distance") else None,
        },
        "aerobic_indicators": {
            "hr_drift_pct": metrics.hr_drift_pct,
            "cardiac_decoupling_pct": metrics.cardiac_decoupling_pct,
            "ef_trend": ef_trend,
            "resp_rate_trend": resp_trend,
        },
        "zone_distribution": zone_dist,
        "weekly_context": {
            "total_hours": round(load.weekly_hours, 1),
            "total_tss": round(load.weekly_tss, 1),
            "ride_count": load.rides_this_week,
            "hour_target": weekly_target,
            "days_remaining_in_week": days_remaining,
        },
        "season": {
            "current_phase": analysis_result.season_phase,
            "target_event": season_cfg.get("target_event", ""),
            "weeks_to_target": weeks_to_target,
        },
        "left_right_balance": lr_balance,
        "next_workout": {
            "type": suggestion.intensity,
            "description": suggestion.description,
            "power_target": _power_target(suggestion.intensity, ftp),
            "rationale": suggestion.reasoning,
        },
        "analysis": {
            "observations": analysis_result.observations,
            "flags": analysis_result.flags,
            "positives": analysis_result.positives,
        },
    }


def _power_target(intensity: str, ftp: int) -> str:
    targets = {
        "recovery": f"0-{int(ftp * 0.55)}W",
        "z2": f"{int(ftp * 0.55)}-{int(ftp * 0.75)}W",
        "tempo": f"{int(ftp * 0.76)}-{int(ftp * 0.90)}W",
        "threshold": f"{int(ftp * 0.91)}-{int(ftp * 1.05)}W",
        "rest": "—",
    }
    return targets.get(intensity, f"~{ftp}W FTP")


def main() -> None:
    api_key = os.environ.get("INTERVALS_API_KEY")
    if not api_key:
        print("ERROR: INTERVALS_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    athlete_id = config.get("intervals_icu", {}).get("athlete_id", "0")
    ftp = config["athlete"]["ftp"]

    client = IntervalsClient(api_key=api_key, athlete_id=athlete_id)

    print("Fetching latest activity...")
    activity = client.get_latest_activity()
    if not activity:
        print("No recent cycling activity found in the last 14 days.", file=sys.stderr)
        sys.exit(1)

    activity_id = activity["id"]
    print(f"Found activity: {activity_id} on {activity.get('start_date_local', '')[:10]}")

    print("Fetching streams...")
    streams_json = client.get_streams(activity_id)

    print("Fetching last 14 days of activities for weekly context...")
    today = datetime.date.today()
    recent_activities = client.list_activities(
        oldest=today - datetime.timedelta(days=14),
        newest=today + datetime.timedelta(days=1),
    )

    ride = load_ride(activity_id=activity_id, streams_json=streams_json)
    metrics = compute_metrics(ride, ftp=ftp)
    analysis_result = analyze(ride, metrics, config)

    from src.intervals_client import build_recent_load_from_activities
    load = build_recent_load_from_activities(recent_activities)
    suggestion = suggest_next_workout(load, config)

    output = build_output(
        activity=activity,
        ride=ride,
        metrics=metrics,
        analysis_result=analysis_result,
        suggestion=suggestion,
        recent_activities=recent_activities,
        config=config,
    )

    data_dir = Path(__file__).parent.parent / "data"
    data_dir.mkdir(exist_ok=True)

    out_path = data_dir / "latest-analysis.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Written to {out_path}")

    history_path = data_dir / "ride-history.json"
    append_history(activity, metrics, analysis_result, history_path)
    print(f"History updated: {history_path}")

    print(f"Ride: {output['ride_type']}, {output['duration_minutes']} min, TSS {output['summary']['tss']}")


if __name__ == "__main__":
    main()
