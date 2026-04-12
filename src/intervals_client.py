"""Intervals.icu API client."""

from __future__ import annotations

import base64
import datetime
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


class IntervalsClient:
    BASE_URL = "https://intervals.icu/api/v1"

    def __init__(self, api_key: str, athlete_id: str = "0"):
        self.athlete_id = athlete_id
        credentials = base64.b64encode(f"API_KEY:{api_key}".encode()).decode()
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Basic {credentials}"

    def _get(self, path: str, **kwargs) -> requests.Response:
        url = f"{self.BASE_URL}{path}"
        response = self.session.get(url, **kwargs)
        response.raise_for_status()
        return response

    def list_activities(
        self,
        oldest: Optional[datetime.date] = None,
        newest: Optional[datetime.date] = None,
    ) -> List[Dict[str, Any]]:
        """Return summary list of activities within a date range."""
        params = {}
        if oldest:
            params["oldest"] = oldest.isoformat()
        if newest:
            params["newest"] = newest.isoformat()
        resp = self._get(f"/athlete/{self.athlete_id}/activities", params=params)
        return resp.json()

    CYCLING_TYPES = {"Ride", "VirtualRide", "EBikeRide", "MountainBikeRide", "GravelRide", "Handcycle"}

    def get_latest_activity(self) -> Optional[Dict[str, Any]]:
        """Return the most recent cycling activity."""
        today = datetime.date.today()
        oldest = today - datetime.timedelta(days=14)
        activities = self.list_activities(oldest=oldest, newest=today + datetime.timedelta(days=1))
        if not activities:
            return None
        rides = [a for a in activities if a.get("type") in self.CYCLING_TYPES]
        if not rides:
            return None
        rides.sort(key=lambda a: a.get("start_date_local", ""), reverse=True)
        return rides[0]

    def get_streams(self, activity_id: str) -> list:
        """Fetch 1-second stream data as parsed JSON (columnar format)."""
        resp = self._get(f"/activity/{activity_id}/streams")
        return resp.json()

    def get_garmin_fit(self, activity_id: str) -> bytes:
        """Fetch the original Garmin FIT file."""
        resp = self._get(f"/activity/{activity_id}/file")
        return resp.content

    def get_intervals_fit(self, activity_id: str) -> bytes:
        """Fetch the Intervals.icu-processed FIT file."""
        resp = self._get(f"/activity/{activity_id}/fit-file")
        return resp.content

    def get_wellness(
        self,
        oldest: Optional[datetime.date] = None,
        newest: Optional[datetime.date] = None,
    ) -> List[Dict[str, Any]]:
        """Return wellness data (weight, resting HR, HRV, sleep)."""
        params = {}
        if oldest:
            params["oldest"] = oldest.isoformat()
        if newest:
            params["newest"] = newest.isoformat()
        resp = self._get(f"/athlete/{self.athlete_id}/wellness", params=params)
        return resp.json()

    def download_activity_files(
        self,
        activity_id: str,
        output_dir: str,
    ) -> Dict[str, Any]:
        """Fetch streams JSON and download FIT files. Returns dict with streams data and FIT paths."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        result: Dict[str, Any] = {}

        result["streams_json"] = self.get_streams(activity_id)

        garmin_path = out / f"{activity_id}.fit"
        garmin_path.write_bytes(self.get_garmin_fit(activity_id))
        result["garmin_fit"] = str(garmin_path)

        intervals_path = out / f"{activity_id}_intervals.fit"
        intervals_path.write_bytes(self.get_intervals_fit(activity_id))
        result["intervals_fit"] = str(intervals_path)

        return result


def build_recent_load_from_activities(activities: List[Dict[str, Any]]) -> "RecentLoad":
    """Build a RecentLoad summary from the activity list API response."""
    from .workout_suggest import RecentLoad
    import datetime

    today = datetime.date.today()
    week_start = today - datetime.timedelta(days=today.weekday())  # Monday

    weekly_hours = 0.0
    weekly_tss = 0.0
    rides_this_week = 0
    consecutive_days = 0
    days_since_rest = 0

    # Sort by date descending
    sorted_acts = sorted(
        activities,
        key=lambda a: a.get("start_date_local", ""),
        reverse=True,
    )

    seen_dates = set()
    for act in sorted_acts:
        date_str = act.get("start_date_local", "")[:10]
        try:
            act_date = datetime.date.fromisoformat(date_str)
        except ValueError:
            continue

        if act_date >= week_start:
            duration_h = act.get("moving_time", 0) / 3600
            weekly_hours += duration_h
            weekly_tss += act.get("training_load", 0) or 0
            rides_this_week += 1

        seen_dates.add(act_date)

    # Count consecutive days ending today
    check = today
    while check in seen_dates:
        consecutive_days += 1
        check -= datetime.timedelta(days=1)

    # Days since last rest day
    check = today
    while check in seen_dates:
        days_since_rest += 1
        check -= datetime.timedelta(days=1)

    return RecentLoad(
        weekly_hours=round(weekly_hours, 2),
        weekly_tss=round(weekly_tss, 1),
        rides_this_week=rides_this_week,
        consecutive_days=consecutive_days,
        days_since_rest=days_since_rest,
        tsb=None,  # would need CTL/ATL history to compute
    )
