"""
Bullmastiff — Configuration
Bromley's 4-day Upper/Lower program. Base Phase (3 waves) + Peak Phase (3 waves).

Main lift: percentage-based autoregulation (+1% 1RM per rep above baseline).
Variation: step loading (fixed % off variation e1RM, sets increase each week).
Accessories: step loading (sets increase each week within each sub-wave).
"""
import os

# ── API Keys ──────────────────────────────────────────────────────────
HEVY_API_KEY = os.environ.get("HEVY_API_KEY", "")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")

# ── Notion IDs ────────────────────────────────────────────────────────
NOTION_LOGBOOK_DB     = os.environ.get("NOTION_LOGBOOK_DB",     "33acbc49-9cfe-8129-b2f3-e116c5997c11")
NOTION_ANALYTICS_PAGE = os.environ.get("NOTION_ANALYTICS_PAGE", "33acbc49-9cfe-8116-81e0-d4c57aa119b1")

# ── Physical Constants ────────────────────────────────────────────────
BODYWEIGHT   = 86.0   # kg
PLATE_STEP   = 2.0    # kg  (smallest increment = 1kg/side)

# ── Program Dates ─────────────────────────────────────────────────────
PROGRAM_START = "2026-05-25"

# ── Hevy IDs ──────────────────────────────────────────────────────────
BULL_FOLDER_ID = 2927589

DAY_ROUTINE_MAP = {
    1: "d2ad3ee9-4f42-4e91-a8a8-baa8b4a49c64",   # D1 Squat
    2: "2f17b0a4-420b-4b41-8340-96df2125e4ba",   # D2 Bench
    3: "b6c29a9d-5e1d-48dc-9207-718c3ef9d558",   # D3 Deadlift
    4: "37108178-16ad-4894-ab7b-6c5995be2014",   # D4 OHP
}

# ── 1RMs (kg) — adjust before starting ───────────────────────────────
# These are used ONLY for weight calculations. Update after testing.
ONE_RM = {
    "squat":    110,
    "bench":    104,
    "deadlift": 162,
    "ohp":       68,
}

# Variation 1RMs — estimated as 80% of corresponding main 1RM.
# Override if you've tested them directly.
def get_variation_1rm(main_key: str) -> float:
    return round(ONE_RM[main_key] * 0.80 / PLATE_STEP) * PLATE_STEP


# ── Day Configuration ─────────────────────────────────────────────────
DAY_CONFIG = {
    1: {
        "name": "Squat",
        "main_key": "squat",
        "var_key":  "front_squat",
        "acc_A": ["bulgarian_ss", "cable_row"],
        "acc_B": ["leg_extension","lat_pulldown"],
    },
    2: {
        "name": "Bench",
        "main_key": "bench",
        "var_key":  "cg_bench",
        "acc_A": ["db_bench",    "hammer_curl"],
        "acc_B": ["db_fly",      "barbell_curl"],
    },
    3: {
        "name": "Deadlift",
        "main_key": "deadlift",
        "var_key":  "rdl",
        "acc_A": ["back_extension","bent_row"],
        "acc_B": ["hamstring_curl","db_row"],
    },
    4: {
        "name": "OHP",
        "main_key": "ohp",
        "var_key":  "btn_press",
        "acc_A": ["db_shoulder_press","skullcrusher"],
        "acc_B": ["lateral_raise",    "rope_pressdown"],
    },
    5: {
        "name": "Upper Back & Traps",
        "main_key": None,   # D5 has no % main lift — step loading only
        "var_key":  None,
        # A-type: heavier compound/power movements
        "acc_A": ["sandbag_cp", "meadows_row", "barbell_shrug", "sandbag_carry"],
        # B-type: lighter, rear delt / upper back health
        "acc_B": ["face_pull", "y_raise", "sandbag_os", "band_pullaparts"],
    },
}


# ── Phase / Wave Prescriptions ────────────────────────────────────────
# BASE PHASE — percentage of main 1RM, 4 sets, amrap last
BASE_MAIN = {
    1: {"pct": 0.70, "reps": 6},   # Wave 1
    2: {"pct": 0.75, "reps": 5},   # Wave 2
    3: {"pct": 0.80, "reps": 4},   # Wave 3
}

# PEAK PHASE — percentage of main 1RM, sets DECREASE by week
PEAK_MAIN = {
    1: {"pct": 0.85, "reps": 3, "sets_by_week": {1: 5, 2: 3, 3: 1}},
    2: {"pct": 0.88, "reps": 2, "sets_by_week": {1: 5, 2: 3, 3: 1}},
    3: {"pct": 0.92, "reps": 1, "sets_by_week": {1: 5, 2: 3, 3: 1}},
}

# BASE VARIATION — step loading, percentage of variation 1RM
# Sets: 3→4→5 across weeks 1-2-3 of each wave
BASE_VAR = {
    1: {"pct": 0.60, "reps": 12},
    2: {"pct": 0.65, "reps": 10},
    3: {"pct": 0.70, "reps":  8},
}

# PEAK VARIATION — sets DECREASE (4→3→2), weight fixed per wave
PEAK_VAR = {
    1: {"pct": 0.75, "reps": 6, "sets_by_week": {1: 4, 2: 3, 3: 2}},
    2: {"pct": 0.80, "reps": 5, "sets_by_week": {1: 4, 2: 3, 3: 2}},
    3: {"pct": 0.85, "reps": 4, "sets_by_week": {1: 4, 2: 3, 3: 2}},
}

# ACCESSORIES — step loading, 2 sub-waves cycling
# A-type: heavier, lower reps. B-type: lighter, higher reps.
# Sets: 2→3→4 across weeks within each accessory sub-wave
ACC_A = {1: {"reps": 10}, 2: {"reps": 8}}   # sub-wave 1 → sub-wave 2
ACC_B = {1: {"reps": 15}, 2: {"reps": 12}}

# 3 main waves per phase = 2.5 accessory sub-waves → cycle: 1, 2, 1, 2...
def get_acc_prescription(phase: str, wave: int, week: int) -> dict:
    """
    Returns {"A": {"sets": n, "reps": r}, "B": {"sets": n, "reps": r}}.
    Accessory sub-wave cycles: wave 1&3 → sub-wave 1, wave 2 → sub-wave 2.
    Sets: week1=2, week2=3, week3=4.
    """
    sub_wave = 1 if wave % 2 == 1 else 2
    n_sets = week + 1  # week1→2, week2→3, week3→4
    return {
        "A": {"sets": n_sets, "reps": ACC_A[sub_wave]["reps"]},
        "B": {"sets": n_sets, "reps": ACC_B[sub_wave]["reps"]},
    }


# ── Exercise Template IDs ─────────────────────────────────────────────
# Maps lift_key → Hevy template_id
LIFT_TO_TID = {
    # Main lifts
    "squat":       "D04AC939",
    "bench":       "79D0BB3A",
    "deadlift":    "C6272009",
    "ohp":         "7B8D84E8",
    # Variations
    "front_squat": "5046D0A9",
    "cg_bench":    "35B51B87",
    "rdl":         "2B4B7310",
    "btn_press":   "883b82a7-8d94-41e9-8efe-644892aa956f",
    # Accessories
    "leg_press":          "C7973E0E",
    "cable_row":          "F1D60854",
    "leg_extension":      "75A4F6C4",
    "lat_pulldown":       "6A6C31A5",
    "db_bench":           "3601968B",
    "hammer_curl":        "7E3BC8B6",
    "db_fly":             "12017185",
    "barbell_curl":       "A5AC6449",
    "back_extension":     "4F5866F8",
    "bent_row":           "55E6546F",
    "hamstring_curl":     "11A123F3",
    "db_row":             "F1E57334",
    "db_shoulder_press":  "878CD1D0",
    "skullcrusher":       "875F585F",
    "lateral_raise":      "422B08F1",
    "rope_pressdown":     "94B7239B",
    # D5: Upper back & traps
    "meadows_row":        "C732C341",
    "barbell_shrug":      "0B841777",
    "sandbag_carry":      "95711844-ad33-4b9e-829d-8ec2d795798a",
    "sandbag_cp":         "65e31abc-d064-44b8-be50-114ab9ac2e2a",
    "sandbag_os":         "0f82c18d-f3de-4983-8641-f1b926a07483",
    "face_pull":          "BE640BA0",
    "rear_delt_db":       "E5988A0A",
    "y_raise":            "F21D5693",
    "band_pullaparts":    "E8D86EE8",
    # Leg press substitute (home gym)
    "bulgarian_ss":       "B5D3A742",
}
TID_TO_LIFT = {v: k for k, v in LIFT_TO_TID.items()}


# ── Strength Standards (multiples of BW) ─────────────────────────────
STRENGTH_STANDARDS = {
    "squat":    {"beginner": 0.75, "intermediate": 1.25, "advanced": 1.75, "elite": 2.25},
    "bench":    {"beginner": 0.50, "intermediate": 1.00, "advanced": 1.50, "elite": 2.00},
    "deadlift": {"beginner": 1.00, "intermediate": 1.50, "advanced": 2.00, "elite": 2.50},
    "ohp":      {"beginner": 0.35, "intermediate": 0.65, "advanced": 1.00, "elite": 1.25},
}

MAIN_LIFTS = {"squat", "bench", "deadlift", "ohp"}
VAR_LIFTS   = {"front_squat", "cg_bench", "rdl", "btn_press"}

# Main key → variation key
MAIN_TO_VAR = {
    "squat":    "front_squat",
    "bench":    "cg_bench",
    "deadlift": "rdl",
    "ohp":      "btn_press",
}


# ── Utility ───────────────────────────────────────────────────────────
def round_to_plate(weight: float) -> float:
    """Round to nearest PLATE_STEP increment."""
    return round(weight / PLATE_STEP) * PLATE_STEP
