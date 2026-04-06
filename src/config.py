"""
Baby Mastiff — Configuration

Bromley's Baby Bully adapted to 5 days (added Row day).
Wave-based progression: 3-week waves of step-loading with AMRAP last set.
Smart increment based on AMRAP performance.

Main lifts: 6-rep range with plus sets (AMRAP).
2nd lifts: 10-rep straight sets, developmental variations.
Accessories: 3-4 x 10-15, bodybuilding.
"""
import os

# ── API Keys ─────────────────────────────────────────────────────────
HEVY_API_KEY = os.environ.get("HEVY_API_KEY", "")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "")

# ── Notion IDs ───────────────────────────────────────────────────────
NOTION_LOGBOOK_DB = os.environ.get("NOTION_LOGBOOK_DB", "")  # TODO: create
NOTION_ANALYTICS_PAGE = os.environ.get("NOTION_ANALYTICS_PAGE", "")  # TODO: create

# ── Physical Constants ───────────────────────────────────────────────
BODYWEIGHT = 86.0  # kg

# ── Program Dates ────────────────────────────────────────────────────
PROGRAM_START = "2026-04-07"  # First Baby Mastiff session

# ── Hevy Folder ──────────────────────────────────────────────────────
BM_FOLDER_ID = None  # TODO: create in Hevy

# ── Hevy Routine IDs (one per day, created later) ────────────────────
DAY_ROUTINE_MAP = {
    1: "",  # BM D1 Squat
    2: "",  # BM D2 Bench
    3: "",  # BM D3 Deadlift
    4: "",  # BM D4 Press
    5: "",  # BM D5 Row
}

# ── Day Configuration ────────────────────────────────────────────────
DAY_CONFIG = {
    1: {"name": "Squat / RDL",      "emoji": "🦵", "focus": "lower_quad",
        "main_key": "squat",    "second_key": "rdl"},
    2: {"name": "Bench / BTN Press", "emoji": "🏋️", "focus": "upper_push",
        "main_key": "bench",    "second_key": "btn_press"},
    3: {"name": "Deadlift / Zercher","emoji": "💀", "focus": "lower_hinge",
        "main_key": "deadlift", "second_key": "zercher_squat"},
    4: {"name": "Press / CG Bench",  "emoji": "🔱", "focus": "upper_push",
        "main_key": "ohp",      "second_key": "cg_bench"},
    5: {"name": "Row / Seal Row",    "emoji": "🚣", "focus": "upper_pull",
        "main_key": "pendlay_row", "second_key": "seal_row"},
}

# ── Wave Progression Scheme ──────────────────────────────────────────
# Each wave = 3 workouts per lift.  Sets escalate, weight stays.
# After wave 3 (5x6+), evaluate AMRAP → determine next wave's weight.
WAVE_SCHEME_MAIN = {
    1: {"sets": 3, "reps": 6, "amrap_last": True},   # 3x6+
    2: {"sets": 4, "reps": 6, "amrap_last": True},   # 4x6+
    3: {"sets": 5, "reps": 6, "amrap_last": True},   # 5x6+
}

WAVE_SCHEME_SECOND = {
    1: {"sets": 3, "reps": 10, "amrap_last": False},  # 3x10
    2: {"sets": 4, "reps": 10, "amrap_last": False},  # 4x10
    3: {"sets": 5, "reps": 10, "amrap_last": False},  # 5x10
}

# ── Increment Rules (kg) ────────────────────────────────────────────
# Based on week-3 AMRAP performance for main lifts.
# 2nd lifts always use standard increment.
INCREMENT = {
    "upper": 2.0,  # base increment for upper body
    "lower": 4.0,  # base increment for lower body
}

LIFT_BODY_PART = {
    "squat": "lower",
    "bench": "upper",
    "deadlift": "lower",
    "ohp": "upper",
    "pendlay_row": "upper",
    # 2nd lifts
    "rdl": "lower",
    "btn_press": "upper",
    "zercher_squat": "lower",
    "cg_bench": "upper",
    "seal_row": "upper",
}

# AMRAP thresholds for main lift increment decision
AMRAP_THRESHOLDS = {
    "surge":    15,  # ≥15 reps → double increment
    "advance":  12,  # 12-14 → standard increment
    "grind":     9,  # 9-11 → standard increment (flagged)
    # ≤8 → stall, repeat weight
}


def get_increment(lift_key: str, amrap_reps: int | None = None) -> float:
    """
    Calculate weight increment for a lift based on AMRAP performance.

    Args:
        lift_key: e.g. 'squat', 'bench'
        amrap_reps: AMRAP reps from week 3 (None for 2nd lifts → standard)

    Returns:
        Weight increment in kg (can be 0 for stall).
    """
    body = LIFT_BODY_PART.get(lift_key, "upper")
    base = INCREMENT[body]

    if amrap_reps is None:
        # 2nd lift: always standard
        return base

    if amrap_reps >= AMRAP_THRESHOLDS["surge"]:
        return base * 2  # SURGE: double increment
    elif amrap_reps >= AMRAP_THRESHOLDS["advance"]:
        return base       # ADVANCE: standard
    elif amrap_reps >= AMRAP_THRESHOLDS["grind"]:
        return base       # GRIND: standard but flagged
    else:
        return 0.0        # STALL: repeat weight


def classify_amrap(reps: int) -> str:
    """Classify AMRAP performance into category."""
    if reps >= AMRAP_THRESHOLDS["surge"]:
        return "SURGE"
    elif reps >= AMRAP_THRESHOLDS["advance"]:
        return "ADVANCE"
    elif reps >= AMRAP_THRESHOLDS["grind"]:
        return "GRIND"
    else:
        return "STALL"


# ── Exercise Database (template_id → metadata) ─────────────────────
# Main + 2nd lifts are tracked for progression.
# Accessories are logged but not auto-progressed.
EXERCISE_DB = {
    # ── D1: Squat / RDL ──────────────────────────────────────
    "38FC1AB9": {
        "name": "Squat to Box (Barbell)",
        "day": 1, "role": "main", "lift_key": "squat",
        "muscle_group": "Piernas", "is_compound": True,
    },
    "2B4B7310": {
        "name": "Romanian Deadlift (Barbell)",
        "day": 1, "role": "second", "lift_key": "rdl",
        "muscle_group": "Isquios", "is_compound": True,
    },
    "75A4F6C4": {
        "name": "Leg Extension (Machine)",
        "day": 1, "role": "accessory", "lift_key": "leg_extension",
        "muscle_group": "Quads", "is_compound": False,
    },
    "A733CC5B": {
        "name": "Walking Lunge (Dumbbell)",
        "day": 1, "role": "accessory", "lift_key": "walking_lunge",
        "muscle_group": "Piernas", "is_compound": True,
    },
    "23A48484": {
        "name": "Cable Crunch",
        "day": 1, "role": "accessory", "lift_key": "cable_crunch",
        "muscle_group": "Core", "is_compound": False,
    },

    # ── D2: Bench / BTN Press ────────────────────────────────
    "79D0BB3A": {
        "name": "Bench Press (Barbell)",
        "day": 2, "role": "main", "lift_key": "bench",
        "muscle_group": "Pecho", "is_compound": True,
    },
    "883b82a7-8d94-41e9-8efe-644892aa956f": {
        "name": "Behind The Neck Press (Barbell)",
        "day": 2, "role": "second", "lift_key": "btn_press",
        "muscle_group": "Hombros", "is_compound": True,
    },
    "4E5257DE": {
        "name": "Lat Pulldown - Close Grip (Cable)",
        "day": 2, "role": "accessory", "lift_key": "lat_pulldown_v",
        "muscle_group": "Espalda", "is_compound": False,
    },
    "A5AC6449": {
        "name": "Bicep Curl (Barbell)",
        "day": 2, "role": "accessory", "lift_key": "barbell_curl",
        "muscle_group": "Bíceps", "is_compound": False,
    },
    # TODO: add chest fly / pec deck for extra pecho volume

    # ── D3: Deadlift / Zercher Squat ─────────────────────────
    "C6272009": {
        "name": "Deadlift (Barbell)",
        "day": 3, "role": "main", "lift_key": "deadlift",
        "muscle_group": "Espalda Baja", "is_compound": True,
    },
    "40C6A9FC": {
        "name": "Zercher Squat",
        "day": 3, "role": "second", "lift_key": "zercher_squat",
        "muscle_group": "Piernas", "is_compound": True,
    },
    "11A123F3": {
        "name": "Seated Leg Curl (Machine)",
        "day": 3, "role": "accessory", "lift_key": "leg_curl",
        "muscle_group": "Isquios", "is_compound": False,
    },
    "F8356514": {
        "name": "Hanging Leg Raise",
        "day": 3, "role": "accessory", "lift_key": "hanging_leg_raise",
        "muscle_group": "Core", "is_compound": False,
    },
    # TODO: add Back Extension for low back

    # ── D4: OHP / CG Bench ───────────────────────────────────
    "7B8D84E8": {
        "name": "Overhead Press (Barbell)",
        "day": 4, "role": "main", "lift_key": "ohp",
        "muscle_group": "Hombros", "is_compound": True,
    },
    "35B51B87": {
        "name": "Bench Press - Close Grip (Barbell)",
        "day": 4, "role": "second", "lift_key": "cg_bench",
        "muscle_group": "Tríceps", "is_compound": True,
    },
    "422B08F1": {
        "name": "Lateral Raise (Dumbbell)",
        "day": 4, "role": "accessory", "lift_key": "lateral_raise",
        "muscle_group": "Hombros", "is_compound": False,
    },
    "93A552C6": {
        "name": "Triceps Pushdown",
        "day": 4, "role": "accessory", "lift_key": "tricep_pushdown",
        "muscle_group": "Tríceps", "is_compound": False,
    },

    # ── D5: Row / Seal Row ───────────────────────────────────
    "018ADC12": {
        "name": "Pendlay Row (Barbell)",
        "day": 5, "role": "main", "lift_key": "pendlay_row",
        "muscle_group": "Espalda", "is_compound": True,
    },
    "2c3103bf-bf30-474f-8396-91ad7021b6cf": {
        "name": "Seal Row (Barbell)",
        "day": 5, "role": "second", "lift_key": "seal_row",
        "muscle_group": "Espalda", "is_compound": True,
    },
    "6FCD7755": {
        "name": "Chest Dip",
        "day": 5, "role": "accessory", "lift_key": "chest_dip",
        "muscle_group": "Pecho", "is_compound": True,
    },
    "37FCC2BB": {
        "name": "Bicep Curl (Dumbbell)",
        "day": 5, "role": "accessory", "lift_key": "bicep_curl_db",
        "muscle_group": "Bíceps", "is_compound": False,
    },
}

# ── Quick Lookups ────────────────────────────────────────────────────
TID_TO_LIFT = {tid: ex["lift_key"] for tid, ex in EXERCISE_DB.items()}
LIFT_TO_TID = {ex["lift_key"]: tid for tid, ex in EXERCISE_DB.items()}
MAIN_LIFTS = {tid: ex for tid, ex in EXERCISE_DB.items() if ex["role"] == "main"}
SECOND_LIFTS = {tid: ex for tid, ex in EXERCISE_DB.items() if ex["role"] == "second"}
ACCESSORY_LIFTS = {tid: ex for tid, ex in EXERCISE_DB.items() if ex["role"] == "accessory"}

# ── Strength Standards (multiples of BW) ────────────────────────────
STRENGTH_STANDARDS = {
    "bench":       {"beginner": 0.50, "intermediate": 1.00, "advanced": 1.50, "elite": 2.00},
    "squat":       {"beginner": 0.75, "intermediate": 1.25, "advanced": 1.75, "elite": 2.25},
    "deadlift":    {"beginner": 1.00, "intermediate": 1.50, "advanced": 2.00, "elite": 2.50},
    "ohp":         {"beginner": 0.35, "intermediate": 0.65, "advanced": 1.00, "elite": 1.25},
    "pendlay_row": {"beginner": 0.50, "intermediate": 0.85, "advanced": 1.20, "elite": 1.50},
}


def round_to_plate(weight: float) -> float:
    """Round weight to nearest 2kg (Juan's smallest increment: 1kg per side)."""
    return round(weight / 2) * 2
