"""Tests for Baby Mastiff progression logic."""
import pytest
from src.config import get_increment, classify_amrap, round_to_plate


class TestClassifyAmrap:
    def test_surge(self):
        assert classify_amrap(15) == "SURGE"
        assert classify_amrap(20) == "SURGE"

    def test_advance(self):
        assert classify_amrap(12) == "ADVANCE"
        assert classify_amrap(14) == "ADVANCE"

    def test_grind(self):
        assert classify_amrap(9) == "GRIND"
        assert classify_amrap(11) == "GRIND"

    def test_stall(self):
        assert classify_amrap(8) == "STALL"
        assert classify_amrap(6) == "STALL"


class TestGetIncrement:
    def test_upper_surge(self):
        assert get_increment("bench", 16) == 4.0  # 2 * 2

    def test_upper_advance(self):
        assert get_increment("bench", 13) == 2.0

    def test_upper_stall(self):
        assert get_increment("bench", 7) == 0.0

    def test_lower_surge(self):
        assert get_increment("squat", 15) == 8.0  # 2 * 4

    def test_lower_advance(self):
        assert get_increment("deadlift", 12) == 4.0

    def test_lower_stall(self):
        assert get_increment("squat", 8) == 0.0

    def test_second_lift_always_standard(self):
        assert get_increment("rdl", None) == 4.0
        assert get_increment("btn_press", None) == 2.0
        assert get_increment("cg_bench", None) == 2.0


class TestRoundToPlate:
    def test_exact(self):
        assert round_to_plate(60) == 60

    def test_round_up(self):
        assert round_to_plate(61) == 60  # banker's rounding: 30.5 → 30

    def test_round_down(self):
        assert round_to_plate(63) == 64  # 63/2=31.5 → 32*2=64

    def test_odd(self):
        assert round_to_plate(59) == 60


class TestWaveDetection:
    """Test wave detection with synthetic data."""

    def test_empty_df(self):
        import pandas as pd
        from src.analytics import detect_waves
        df = pd.DataFrame()
        result = detect_waves(df)
        # Should return empty states for all lifts
        assert all(v["total_sessions"] == 0 for v in result.values())

    def test_single_session(self):
        import pandas as pd
        from src.analytics import detect_waves

        df = pd.DataFrame([{
            "date": pd.Timestamp("2026-04-07"),
            "hevy_id": "test1",
            "exercise_template_id": "38FC1AB9",  # squat
            "role": "main",
            "lift_key": "squat",
            "max_weight": 60,
            "n_sets": 3,
            "reps_list": [6, 6, 12],
            "amrap_reps": 12,
            "e1rm": 84,
        }])

        waves = detect_waves(df)
        assert waves["squat"]["wave"] == 1
        assert waves["squat"]["week_in_wave"] == 1
        assert waves["squat"]["current_weight"] == 60
