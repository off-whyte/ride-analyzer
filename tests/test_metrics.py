"""Unit tests for metrics.py against the known i138521071 ride values."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from src.ride_parser import parse_streams_csv, load_ride
from src.metrics import compute_metrics, normalized_power, zone_distribution

TEST_DATA = os.path.join(os.path.dirname(__file__), "test_data")
STREAMS_CSV = os.path.join(TEST_DATA, "i138521071_streams.csv")
GARMIN_FIT = os.path.join(TEST_DATA, "i138521071.fit")
INDOOR_FIT = os.path.join(TEST_DATA, "i138521071_Indoor_Cycling.fit")

FTP = 250


@pytest.fixture
def streams():
    return parse_streams_csv(STREAMS_CSV)


@pytest.fixture
def ride():
    return load_ride(
        activity_id="i138521071",
        streams_path=STREAMS_CSV,
        garmin_fit_path=GARMIN_FIT,
    )


@pytest.fixture
def metrics(ride):
    return compute_metrics(ride, ftp=FTP)


class TestStreamsParser:
    def test_parses_correct_number_of_points(self, streams):
        # 90.3 min = 5420 seconds → 5421 rows (0-indexed)
        assert len(streams) >= 5400
        assert len(streams) <= 5450

    def test_first_point(self, streams):
        p = streams[0]
        assert p.time == 0
        assert p.watts == 123
        assert p.cadence == 48
        assert p.heartrate == 79

    def test_has_respiration_data(self, streams):
        resp_points = [p for p in streams if p.respiration is not None]
        assert len(resp_points) > 1000

    def test_has_balance_data(self, streams):
        balance_points = [p for p in streams if p.balance is not None]
        assert len(balance_points) > 1000


class TestNormalizedPower:
    def test_known_np(self, ride):
        """Plan says NP should be ~150W."""
        watts = ride.watts_series
        np = normalized_power(watts)
        assert 145 <= np <= 155, f"NP={np:.1f}W, expected ~150W"

    def test_np_gt_avg(self, ride):
        """NP is always >= avg power for non-constant efforts."""
        watts = ride.watts_series
        np = normalized_power(watts)
        avg = sum(watts) / len(watts)
        assert np >= avg


class TestMetricsComputed:
    def test_avg_power(self, metrics):
        """Plan says avg power ~146W."""
        assert 140 <= metrics.avg_power <= 152, f"avg_power={metrics.avg_power}"

    def test_avg_hr(self, metrics):
        """Plan says avg HR ~137 bpm."""
        assert 133 <= metrics.avg_hr <= 141, f"avg_hr={metrics.avg_hr}"

    def test_max_hr(self, metrics):
        """Plan says max HR ~155 bpm."""
        assert 150 <= metrics.max_hr <= 160, f"max_hr={metrics.max_hr}"

    def test_if_at_ftp250(self, metrics):
        """Plan says IF=0.60 at FTP=250."""
        assert 0.58 <= metrics.intensity_factor <= 0.62, f"IF={metrics.intensity_factor}"

    def test_tss_at_ftp250(self, metrics):
        """TSS = IF² × hours × 100. At IF=0.60 for 90.3 min: ~54.
        (The plan stated 32.6 but that's for ~54 min, not 90 min — plan has a typo.)"""
        assert 50 <= metrics.tss <= 60, f"TSS={metrics.tss}"

    def test_hr_drift(self, metrics):
        """Plan says HR drift ~4.2%."""
        assert metrics.hr_drift_pct is not None
        assert 2.0 <= metrics.hr_drift_pct <= 7.0, f"hr_drift={metrics.hr_drift_pct}%"

    def test_ef_windows(self, metrics):
        """Plan says EF range 0.98–1.13 W/bpm."""
        assert len(metrics.ef_windows) > 0
        ef_vals = [ef for _, ef in metrics.ef_windows]
        assert min(ef_vals) >= 0.85, f"EF min too low: {min(ef_vals)}"
        assert max(ef_vals) <= 1.30, f"EF max too high: {max(ef_vals)}"

    def test_duration(self, metrics):
        """Plan says duration ~5420 seconds."""
        assert 5400 <= metrics.duration_seconds <= 5440

    def test_avg_cadence(self, metrics):
        """Plan says avg cadence ~91 rpm."""
        assert 85 <= metrics.avg_cadence <= 97


class TestZoneDistribution:
    def test_mostly_z2(self, metrics):
        """This is classified as an endurance/Z2 ride."""
        pcts = metrics.zones.as_percents()
        z2_plus = pcts["z1"] + pcts["z2"]
        assert z2_plus > 50, f"Expected >50% in Z1/Z2, got {z2_plus:.1f}%"

    def test_zones_sum_to_100(self, metrics):
        pcts = metrics.zones.as_percents()
        total = sum(pcts.values())
        assert abs(total - 100) < 0.01


class TestAnalysis:
    def test_ride_classification(self, ride, metrics):
        from src.analysis import classify_ride
        classification = classify_ride(metrics)
        assert classification.name == "Endurance/Z2"

    def test_season_phase_april(self):
        import datetime
        from src.analysis import get_season_phase
        config = {
            "season": {
                "phases": [
                    {"name": "base", "start": "2026-04-01", "end": "2026-05-31"},
                    {"name": "build1", "start": "2026-06-01", "end": "2026-07-15"},
                ]
            }
        }
        phase = get_season_phase(config, datetime.date(2026, 4, 9))
        assert phase == "base"
