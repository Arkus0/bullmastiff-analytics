"""Tests for Bullmastiff progression logic."""
import pytest
import pandas as pd
from src.config import round_to_plate, ONE_RM, get_acc_prescription
from src.analytics import (
    get_plan_position, compute_main_weight, weight_jump_from_amrap,
    amrap_classification, next_session_plan,
)


class TestRoundToPlate:
    def test_exact(self):
        assert round_to_plate(60) == 60.0
    def test_round_nearest_2(self):
        assert round_to_plate(61) == 60.0
        assert round_to_plate(63) == 64.0
    def test_float(self):
        assert round_to_plate(77.0) == 76.0


class TestPlanPosition:
    def _df(self, lift_key, n_sessions):
        rows = [{"hevy_id": f"s{i}", "lift_key": lift_key, "role": "main",
                 "amrap_reps": 8, "max_weight": 80.0,
                 "date": pd.Timestamp(f"2026-0{(i//28)+1}-{(i%28)+1:02d}")}
                for i in range(n_sessions)]
        return pd.DataFrame(rows)

    def test_empty(self):
        pos = get_plan_position(pd.DataFrame())
        for lk in ["squat", "bench", "deadlift", "ohp"]:
            assert pos[lk]["phase"] == "base"
            assert pos[lk]["wave"] == 1
            assert pos[lk]["week"] == 1

    def test_base_wave2(self):
        df = self._df("squat", 3)  # 3 sessions → start wave 2
        pos = get_plan_position(df)
        assert pos["squat"]["phase"] == "base"
        assert pos["squat"]["wave"] == 2
        assert pos["squat"]["week"] == 1

    def test_base_wave1_week2(self):
        df = self._df("squat", 1)
        pos = get_plan_position(df)
        assert pos["squat"]["wave"] == 1
        assert pos["squat"]["week"] == 2

    def test_peak_start(self):
        df = self._df("squat", 9)
        pos = get_plan_position(df)
        assert pos["squat"]["phase"] == "peak"
        assert pos["squat"]["wave"] == 1
        assert pos["squat"]["week"] == 1

    def test_lifts_independent(self):
        # squat has 3 sessions, bench has 0
        rows = [{"hevy_id": f"s{i}", "lift_key": "squat", "role": "main",
                 "amrap_reps": 8, "max_weight": 80.0,
                 "date": pd.Timestamp(f"2026-01-{i+1:02d}")}
                for i in range(3)]
        df = pd.DataFrame(rows)
        pos = get_plan_position(df)
        assert pos["squat"]["wave"] == 2
        assert pos["bench"]["wave"] == 1


class TestWeightJump:
    def test_zero_extra(self):
        assert weight_jump_from_amrap("squat", 6, 6) == 0.0

    def test_5_extra_squat(self):
        # 5 × (110 × 0.01) = 5.5 → rounded to 6.0
        assert weight_jump_from_amrap("squat", 11, 6) == pytest.approx(6.0)

    def test_3_extra_bench(self):
        # 3 × (104 × 0.01) = 3.12 → rounded to 4.0
        assert weight_jump_from_amrap("bench", 9, 6) == pytest.approx(4.0)

    def test_1_extra_ohp(self):
        # 1 × (68 × 0.01) = 0.68 → rounded to 0.0 (< 1kg/side)
        assert weight_jump_from_amrap("ohp", 7, 6) == pytest.approx(0.0)


class TestAmrapClassification:
    def test_surge_5_extra(self):
        cat, _ = amrap_classification(11, 6)
        assert cat == "SURGE"

    def test_advance_2_extra(self):
        cat, _ = amrap_classification(8, 6)
        assert cat == "ADVANCE"

    def test_grind_no_extra(self):
        cat, _ = amrap_classification(6, 6)
        assert cat == "GRIND"

    def test_grind_below_baseline(self):
        cat, _ = amrap_classification(4, 6)
        assert cat == "GRIND"


class TestAccProgression:
    def test_base_w1_week1(self):
        acc = get_acc_prescription("base", 1, 1)
        assert acc["A"]["sets"] == 2
        assert acc["A"]["reps"] == 10
        assert acc["B"]["sets"] == 2
        assert acc["B"]["reps"] == 15

    def test_base_w1_week3(self):
        acc = get_acc_prescription("base", 1, 3)
        assert acc["A"]["sets"] == 4
        assert acc["B"]["sets"] == 4

    def test_base_w2_subwave2_reps(self):
        acc = get_acc_prescription("base", 2, 1)
        assert acc["A"]["reps"] == 8
        assert acc["B"]["reps"] == 12

    def test_peak_w1_subwave1(self):
        acc = get_acc_prescription("peak", 1, 1)
        assert acc["A"]["reps"] == 10   # sub-wave 1 (odd wave)
        assert acc["B"]["reps"] == 15


class TestNextSessionPlan:
    def test_empty_df_d1(self):
        plan = next_session_plan(pd.DataFrame(), 1)
        assert plan["phase"] == "base"
        assert plan["wave"] == 1
        assert plan["week"] == 1
        assert plan["main"]["sets"] == 4
        assert plan["main"]["reps"] == 6
        assert plan["main"]["weight"] == round_to_plate(ONE_RM["squat"] * 0.70)
        assert plan["variation"]["sets"] == 3   # week 1 → 3 sets
        assert plan["variation"]["reps"] == 12

    def test_empty_df_d3_deadlift(self):
        plan = next_session_plan(pd.DataFrame(), 3)
        assert plan["main"]["lift_key"] == "deadlift"
        assert plan["main"]["weight"] == round_to_plate(ONE_RM["deadlift"] * 0.70)
