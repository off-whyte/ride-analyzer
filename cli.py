#!/usr/bin/env python3
"""Ride Analyzer CLI."""

import argparse
import datetime
import os
import sys
import tempfile
from pathlib import Path

import yaml


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_client(config: dict):
    from src.intervals_client import IntervalsClient
    api_key = config["intervals_icu"]["api_key"]
    if api_key == "YOUR_API_KEY_HERE":
        # Fall back to environment variable
        api_key = os.environ.get("INTERVALS_API_KEY", "")
    if not api_key:
        print("Error: Set api_key in config.yaml or INTERVALS_API_KEY env var.", file=sys.stderr)
        sys.exit(1)
    athlete_id = config["intervals_icu"].get("athlete_id", "0")
    return IntervalsClient(api_key=api_key, athlete_id=athlete_id)


def analyze_activity(activity_id: str, config: dict, streams_path=None, streams_json=None, garmin_fit=None, intervals_fit=None):
    from src.ride_parser import load_ride
    from src.metrics import compute_metrics
    from src.analysis import analyze
    from src.report import render_report

    ftp = config["athlete"]["ftp"]

    ride = load_ride(
        activity_id=activity_id,
        streams_path=streams_path,
        streams_json=streams_json,
        garmin_fit_path=garmin_fit,
        intervals_fit_path=intervals_fit,
    )

    if not ride.streams:
        print(f"Error: No stream data found for {activity_id}", file=sys.stderr)
        sys.exit(1)

    m = compute_metrics(ride, ftp=ftp)
    result = analyze(ride, m, config)

    # Build a minimal load for suggestion (no historical data in this path)
    from src.workout_suggest import RecentLoad, suggest_next_workout
    load = RecentLoad(
        weekly_hours=0,
        weekly_tss=m.tss or 0,
        rides_this_week=1,
        consecutive_days=1,
        days_since_rest=1,
        tsb=None,
    )
    suggestion = suggest_next_workout(load, config)

    report = render_report(
        activity_id=activity_id,
        m=m,
        result=result,
        suggestion=suggestion,
    )
    print(report)


def cmd_activity(args, config):
    """Analyze a specific activity ID, fetching data from API."""
    client = get_client(config)
    activity_id = args.activity_id

    print(f"Fetching data for activity {activity_id}...", file=sys.stderr)
    with tempfile.TemporaryDirectory() as tmpdir:
        data = client.download_activity_files(activity_id, tmpdir)
        analyze_activity(
            activity_id=activity_id,
            config=config,
            streams_json=data.get("streams_json"),
            garmin_fit=data.get("garmin_fit"),
            intervals_fit=data.get("intervals_fit"),
        )


def cmd_latest(args, config):
    """Analyze the most recent activity."""
    client = get_client(config)
    print("Fetching latest activity...", file=sys.stderr)
    activity = client.get_latest_activity()
    if not activity:
        print("No recent activities found.", file=sys.stderr)
        sys.exit(1)
    activity_id = activity["id"]
    print(f"Found: {activity_id} — {activity.get('name', 'unnamed')}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmpdir:
        data = client.download_activity_files(activity_id, tmpdir)
        analyze_activity(
            activity_id=activity_id,
            config=config,
            streams_json=data.get("streams_json"),
            garmin_fit=data.get("garmin_fit"),
            intervals_fit=data.get("intervals_fit"),
        )


def cmd_local(args, config):
    """Analyze from local files (for testing without API key)."""
    analyze_activity(
        activity_id=args.activity_id or "local",
        config=config,
        streams_path=args.streams,
        garmin_fit=args.garmin_fit,
        intervals_fit=args.intervals_fit,
    )


def cmd_weekly(args, config):
    """Show weekly training summary."""
    client = get_client(config)
    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())

    print(f"Fetching activities from {week_start} to {today}...", file=sys.stderr)
    activities = client.list_activities(oldest=week_start, newest=today)

    from src.intervals_client import build_recent_load_from_activities
    from src.workout_suggest import suggest_next_workout
    from src.analysis import get_season_phase

    load = build_recent_load_from_activities(activities)
    phase = get_season_phase(config)
    target = config["training"]["weekly_hour_target"]

    print(f"## Weekly Summary — {week_start} to {today}")
    print(f"Phase: {phase.upper()}")
    print(f"Rides: {load.rides_this_week} | Hours: {load.weekly_hours:.1f}/{target} | TSS: {load.weekly_tss:.0f}")
    print(f"Consecutive days: {load.consecutive_days} | Days since rest: {load.days_since_rest}")
    print()

    suggestion = suggest_next_workout(load, config)
    print(f"**Next workout:** {suggestion.title}")
    print(suggestion.description)
    print(f"Reason: {suggestion.reasoning}")


def cmd_season_status(args, config):
    """Show season progress."""
    from src.analysis import get_season_phase

    today = datetime.date.today()
    phase = get_season_phase(config)
    target_date = datetime.date.fromisoformat(config["season"]["target_date"])
    days_to_target = (target_date - today).days
    target_event = config["season"]["target_event"]

    print(f"## Season Status — {today}")
    print(f"Current phase: **{phase.upper()}**")
    print(f"Target event: {target_event} ({target_date})")
    print(f"Days to target: {days_to_target}")

    phases = config["season"]["phases"]
    for p in phases:
        start = datetime.date.fromisoformat(p["start"])
        end = datetime.date.fromisoformat(p["end"])
        marker = " ← NOW" if p["name"] == phase else ""
        print(f"  {p['name']:10} {start} – {end}{marker}")


def main():
    parser = argparse.ArgumentParser(description="Ride Analyzer — post-ride analysis tuned to your season")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")

    subparsers = parser.add_subparsers(dest="command")

    # --latest
    p_latest = subparsers.add_parser("latest", help="Analyze most recent ride (fetches from API)")
    p_latest.set_defaults(func=cmd_latest)

    # --activity-id
    p_act = subparsers.add_parser("activity", help="Analyze a specific activity (fetches from API)")
    p_act.add_argument("activity_id", help="Intervals.icu activity ID (e.g. i138521071)")
    p_act.set_defaults(func=cmd_activity)

    # --local (for testing)
    p_local = subparsers.add_parser("local", help="Analyze from local files")
    p_local.add_argument("--streams", help="Path to streams CSV")
    p_local.add_argument("--garmin-fit", help="Path to Garmin FIT file")
    p_local.add_argument("--intervals-fit", help="Path to Intervals.icu FIT file")
    p_local.add_argument("--activity-id", default="local", help="Activity ID label")
    p_local.set_defaults(func=cmd_local)

    # --weekly
    p_weekly = subparsers.add_parser("weekly", help="Weekly training summary and next workout suggestion")
    p_weekly.set_defaults(func=cmd_weekly)

    # --season-status
    p_season = subparsers.add_parser("season", help="Season phase progress")
    p_season.set_defaults(func=cmd_season_status)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    config = load_config(args.config)
    args.func(args, config)


if __name__ == "__main__":
    main()
