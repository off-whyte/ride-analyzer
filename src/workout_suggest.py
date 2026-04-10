"""Suggest next workout based on recent load and season phase."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import List, Optional

from .analysis import get_season_phase


@dataclass
class RecentLoad:
    weekly_hours: float
    weekly_tss: float
    rides_this_week: int
    consecutive_days: int   # days with a ride ending today
    days_since_rest: int    # days since last full rest day
    tsb: Optional[float]    # training stress balance (CTL - ATL), if available


@dataclass
class WorkoutSuggestion:
    title: str
    description: str
    duration_minutes: int
    intensity: str          # "recovery", "z2", "tempo", "threshold", "rest"
    reasoning: str


def suggest_next_workout(
    load: RecentLoad,
    config: dict,
    date: Optional[datetime.date] = None,
) -> WorkoutSuggestion:
    if date is None:
        date = datetime.date.today()

    phase = get_season_phase(config, date)
    weekly_target = config.get("training", {}).get("weekly_hour_target", 10)
    rides_target = config.get("training", {}).get("rides_per_week_target", 5)

    hours_remaining = weekly_target - load.weekly_hours
    days_left_in_week = 7 - date.weekday()  # weekday() 0=Mon, 6=Sun

    # Forced rest if too many consecutive days
    if load.consecutive_days >= 4 or load.days_since_rest >= 4:
        return WorkoutSuggestion(
            title="Rest Day",
            description="Full rest or very easy 20-minute walk.",
            duration_minutes=0,
            intensity="rest",
            reasoning=(
                f"{load.consecutive_days} consecutive riding days. Recovery is where adaptation happens — "
                f"take a full rest day."
            ),
        )

    # Recovery spin after heavy load
    if load.days_since_rest == 3 and load.weekly_hours > 7:
        return WorkoutSuggestion(
            title="Recovery Spin",
            description="45-minute easy spin, keep HR in Z1, no structure.",
            duration_minutes=45,
            intensity="recovery",
            reasoning=(
                f"3 days in a row with {load.weekly_hours:.1f} hours accumulated. "
                f"Active recovery will keep your legs moving without adding fatigue."
            ),
        )

    if phase == "base":
        return _suggest_base(load, weekly_target, hours_remaining, days_left_in_week)
    elif phase == "build1":
        return _suggest_build1(load, hours_remaining, days_left_in_week)
    elif phase in ("build2", "peak"):
        return _suggest_peak(load, hours_remaining, days_left_in_week)
    else:
        return WorkoutSuggestion(
            title="Easy Ride",
            description="Off-season — keep it fun and easy.",
            duration_minutes=60,
            intensity="z2",
            reasoning="Off-season maintenance. No structured training prescribed.",
        )


def _suggest_base(load: RecentLoad, target: float, remaining: float, days_left: int) -> WorkoutSuggestion:
    if remaining <= 0:
        return WorkoutSuggestion(
            title="Rest Day",
            description="Weekly hour target hit. Take a rest day.",
            duration_minutes=0,
            intensity="rest",
            reasoning=f"You've hit your {target}-hour target for the week. Well done.",
        )

    avg_needed = remaining / max(days_left, 1)

    # Fresh after rest — go long
    if load.days_since_rest == 0 or load.consecutive_days == 0:
        duration = min(150, max(90, int(avg_needed * 60 * 1.2)))
        return WorkoutSuggestion(
            title="Long Z2 Ride",
            description=(
                f"Your longest Z2 ride of the week. Target {duration} minutes at Z2 power "
                f"({int(0.6 * 250)}-{int(0.75 * 250)}W). Keep HR controlled, no surges."
            ),
            duration_minutes=duration,
            intensity="z2",
            reasoning=(
                f"Fresh after rest, {remaining:.1f} hours left in the week, {days_left} days remaining. "
                f"Best day for a long aerobic effort."
            ),
        )

    # Mid-week tracking toward target
    if remaining > 2:
        duration = max(60, min(120, int(avg_needed * 60)))
        return WorkoutSuggestion(
            title="Z2 Endurance",
            description=(
                f"{duration}-minute Z2 ride. Power in the lower half of Z2 if tired, "
                f"upper half if feeling good. One short climb or surge is fine."
            ),
            duration_minutes=duration,
            intensity="z2",
            reasoning=(
                f"{load.weekly_hours:.1f} hours done, {remaining:.1f} to go with {days_left} days left. "
                f"Steady Z2 work keeps you on track."
            ),
        )

    # Close to target, easy day
    return WorkoutSuggestion(
        title="Easy Flush Ride",
        description="45-60 minute easy spin to round out the week. No intensity.",
        duration_minutes=50,
        intensity="z2",
        reasoning=(
            f"Only {remaining:.1f} hours left to hit target with {days_left} days remaining. "
            f"Easy volume to close the week without digging a hole."
        ),
    )


def _suggest_build1(load: RecentLoad, remaining: float, days_left: int) -> WorkoutSuggestion:
    if load.days_since_rest <= 1 and remaining > 2:
        return WorkoutSuggestion(
            title="Sweet Spot Intervals",
            description=(
                "3x10 minutes at 88-93% FTP (220-233W) with 5-minute easy recovery between. "
                "Warm up 15 min, cool down 10 min."
            ),
            duration_minutes=90,
            intensity="tempo",
            reasoning="Fresh day in build phase — time to target sweet spot for threshold development.",
        )
    return WorkoutSuggestion(
        title="Z2 Aerobic Maintenance",
        description="90-minute Z2 ride. Support recovery while maintaining aerobic base.",
        duration_minutes=90,
        intensity="z2",
        reasoning="Balancing intensity from recent days with aerobic maintenance.",
    )


def _suggest_peak(load: RecentLoad, remaining: float, days_left: int) -> WorkoutSuggestion:
    if load.days_since_rest <= 1:
        return WorkoutSuggestion(
            title="CX-Specific Efforts",
            description=(
                "8x1-minute at 120%+ FTP (300W+) with 3-minute easy between. "
                "Focus on explosive start and power repeatability. Warm up 20 min."
            ),
            duration_minutes=75,
            intensity="threshold",
            reasoning="Peak/race phase: short explosive efforts train CX-specific power.",
        )
    return WorkoutSuggestion(
        title="Active Recovery",
        description="45-minute easy spin. Keep HR under Z2.",
        duration_minutes=45,
        intensity="recovery",
        reasoning="Recovery between peak-phase intensity sessions.",
    )
