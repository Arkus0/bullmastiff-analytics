"""
Baby Mastiff — Analytics & Autoprogression

Fetch workouts from Hevy, detect waves, evaluate AMRAP performance,
compute next wave's weights, and update Hevy routines.

Wave Structure (per lift):
  Wave N = 3 sessions at same weight
    Session 1: 3x6+ (AMRAP last set)
    Session 2: 4x6+ (AMRAP last set)
    Session 3: 5x6+ (AMRAP last set)
  After session 3: evaluate week-3 AMRAP → determine weight change

2nd Lifts:
  Same wave structure but 3/4/5 x10 straight sets (no AMRAP).
  Always standard increment after each wave.
"""
import os
import time
import urllib.request
import json
from datetime import datetime

import pandas as pd
import numpy as np

from src.config import (
    EXERCISE_DB, TID_TO_LIFT, LIFT_TO_TID, MAIN_LIFTS, SECOND_LIFTS,
    DAY_CONFIG, DAY_ROUTINE_MAP, BODYWEIGHT, STRENGTH_STANDARDS,
    WAVE_SCHEME_MAIN, WAVE_SCHEME_SECOND, LIFT_BODY_PART, INCREMENT,
    get_increment, classify_amrap, round_to_plate,
)

HEVY_API_KEY = os.environ.get("HEVY_API_KEY", "")
HEVY_BASE = "https://api.hevyapp.com/v1"


# ═══════════════════════════════════════════════════════════════════════
#  DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════

def _hevy_get(endpoint: str) -> dict:
    """GET request to Hevy API with rate limiting."""
    time.sleep(0.35)
    url = f"{HEVY_BASE}{endpoint}"
    req = urllib.request.Request(url, headers={"api-key": HEVY_API_KEY})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())


def fetch_bm_workouts() -> list[dict]:
    """Fetch all Baby Mastiff workouts (matched by title prefix 'BM D')."""
    all_workouts = []
    page = 1
    while True:
        data = _hevy_get(f"/workouts?page={page}&pageSize=10")
        wks = data.get("workouts", [])
        if not wks:
            break
        for w in wks:
            title = w.get("title", "")
            if title.startswith("BM D") or title.startswith("Baby Mastiff"):
                all_workouts.append(w)
        if page >= data.get("page_count", 1):
            break
        page += 1
    return all_workouts


def workouts_to_dataframe(workouts: list[dict]) -> pd.DataFrame:
    """Convert raw Hevy workouts to flat DataFrame. One row per exercise."""
    rows = []
    for w in workouts:
        date = w["start_time"][:10]
        title = w["title"]
        hevy_id = w["id"]

        # Extract day number from title (e.g. "BM D1 Squat / RDL")
        day_num = _extract_day_num(title)

        start = datetime.fromisoformat(w["start_time"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(w["end_time"].replace("Z", "+00:00"))
        duration_min = round((end - start).total_seconds() / 60)
        description = w.get("description", "") or ""

        for ex in w.get("exercises", []):
            tid = ex.get("exercise_template_id", "")
            sets = ex.get("sets", [])
            working = [s for s in sets if s.get("type") in
                        ("normal", "failure", "dropset", None)]
            if not working:
                working = sets

            reps_list = [s.get("reps", 0) or 0 for s in working]
            weights = [s.get("weight_kg", 0) or 0 for s in working]
            volume = sum(wt * r for wt, r in zip(weights, reps_list))

            max_w = max(weights) if weights else 0
            reps_at_max = [r for wt, r in zip(weights, reps_list) if wt == max_w]
            max_r = max(reps_at_max) if reps_at_max else 0

            # Epley e1RM
            if max_w > 0 and max_r > 0:
                e1rm = round(max_w * (1 + max_r / 30), 1) if max_r > 1 else max_w
            else:
                e1rm = 0

            # Identify role from config
            ex_info = EXERCISE_DB.get(tid, {})
            role = ex_info.get("role", "unknown")
            lift_key = ex_info.get("lift_key", "")

            # Detect AMRAP: last set with significantly more reps than prescribed
            is_amrap_set = False
            amrap_reps = 0
            if role == "main" and len(reps_list) >= 3:
                # Last set is the AMRAP — it's always the last one
                amrap_reps = reps_list[-1]
                # Consider it AMRAP if last set ≥ 6 reps (minimum target)
                is_amrap_set = amrap_reps >= 6

            rows.append({
                "date": pd.Timestamp(date),
                "hevy_id": hevy_id,
                "workout_title": title,
                "day_num": day_num,
                "day_name": DAY_CONFIG.get(day_num, {}).get("name", title),
                "duration_min": duration_min,
                "description": description,
                "exercise": ex["title"],
                "exercise_template_id": tid,
                "role": role,
                "lift_key": lift_key,
                "n_sets": len(working),
                "reps_list": reps_list,
                "reps_str": ",".join(str(r) for r in reps_list),
                "total_reps": sum(reps_list),
                "max_weight": max_w,
                "max_reps_at_max": max_r,
                "volume_kg": volume,
                "e1rm": e1rm,
                "top_set": f"{max_w}kg x {max_r}" if max_w > 0 else f"BW x {max_r}",
                "is_bodyweight": max_w == 0,
                "amrap_reps": amrap_reps if is_amrap_set else None,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["date", "day_num"]).reset_index(drop=True)
    return df


def _extract_day_num(title: str) -> int | None:
    """Extract day number from workout title."""
    import re
    m = re.search(r"D(\d)", title)
    return int(m.group(1)) if m else None


# ═══════════════════════════════════════════════════════════════════════
#  WAVE DETECTION & PROGRESSION
# ═══════════════════════════════════════════════════════════════════════

def detect_waves(df: pd.DataFrame) -> dict:
    """
    Analyze workout history and detect wave state for each lift.

    Returns dict keyed by lift_key:
    {
        "squat": {
            "wave": 3,
            "week_in_wave": 2,   # 1-3
            "current_weight": 60,
            "sessions": [...],
            "amrap_history": [...],
            "last_amrap": 14,
            "classification": "ADVANCE",
            "next_weight": 62,
            "next_increment": 2,
        }, ...
    }
    """
    result = {}

    if df.empty:
        for tid, ex in {**MAIN_LIFTS, **SECOND_LIFTS}.items():
            result[ex["lift_key"]] = _empty_wave_state(ex["lift_key"], ex["role"])
        return result

    for tid, ex in {**MAIN_LIFTS, **SECOND_LIFTS}.items():
        lift_key = ex["lift_key"]
        role = ex["role"]

        # Get all sessions for this lift, chronological
        lift_df = df[df["exercise_template_id"] == tid].copy()
        if lift_df.empty:
            result[lift_key] = _empty_wave_state(lift_key, role)
            continue

        lift_df = lift_df.sort_values("date").reset_index(drop=True)

        # Group by weight to find waves (wave = consecutive sessions at same weight)
        sessions = []
        for _, row in lift_df.iterrows():
            sessions.append({
                "date": row["date"],
                "weight": row["max_weight"],
                "n_sets": row["n_sets"],
                "reps_list": row["reps_list"],
                "amrap_reps": row.get("amrap_reps"),
                "e1rm": row["e1rm"],
                "hevy_id": row["hevy_id"],
            })

        # Current wave: sessions at the same weight at the end
        current_weight = sessions[-1]["weight"]
        current_wave_sessions = []
        for s in reversed(sessions):
            if s["weight"] == current_weight:
                current_wave_sessions.insert(0, s)
            else:
                break

        week_in_wave = len(current_wave_sessions)

        # Count total waves (weight changes = wave transitions)
        wave_count = 1
        prev_w = sessions[0]["weight"] if sessions else 0
        for s in sessions[1:]:
            if s["weight"] != prev_w:
                wave_count += 1
                prev_w = s["weight"]

        # AMRAP analysis (main lifts only)
        amrap_history = []
        last_amrap = None
        classification = None
        next_increment = 0
        next_weight = current_weight

        if role == "main":
            amrap_history = [
                {"date": s["date"], "weight": s["weight"],
                 "reps": s["amrap_reps"], "week": i + 1}
                for i, s in enumerate(current_wave_sessions)
                if s["amrap_reps"] is not None
            ]
            if current_wave_sessions:
                last_amrap = current_wave_sessions[-1].get("amrap_reps")

            # If wave is complete (3 sessions), classify and compute next
            if week_in_wave >= 3 and last_amrap is not None:
                classification = classify_amrap(last_amrap)
                next_increment = get_increment(lift_key, last_amrap)
                next_weight = round_to_plate(current_weight + next_increment)
        else:
            # 2nd lifts: always standard increment after 3 sessions
            if week_in_wave >= 3:
                next_increment = get_increment(lift_key, None)
                next_weight = round_to_plate(current_weight + next_increment)
                classification = "STANDARD"

        result[lift_key] = {
            "wave": wave_count,
            "week_in_wave": min(week_in_wave, 3),
            "current_weight": current_weight,
            "sessions": current_wave_sessions,
            "amrap_history": amrap_history,
            "last_amrap": last_amrap,
            "classification": classification,
            "next_weight": next_weight,
            "next_increment": next_increment,
            "total_sessions": len(sessions),
            "role": role,
        }

    return result


def _empty_wave_state(lift_key: str, role: str) -> dict:
    return {
        "wave": 0, "week_in_wave": 0, "current_weight": 0,
        "sessions": [], "amrap_history": [], "last_amrap": None,
        "classification": None, "next_weight": 0, "next_increment": 0,
        "total_sessions": 0, "role": role,
    }


# ═══════════════════════════════════════════════════════════════════════
#  HEVY ROUTINE UPDATES
# ═══════════════════════════════════════════════════════════════════════

def build_routine_exercises(day_num: int, waves: dict) -> list[dict]:
    """Build Hevy routine exercise list for a given day."""
    day_cfg = DAY_CONFIG[day_num]
    main_key = day_cfg["main_key"]
    second_key = day_cfg["second_key"]
    main_tid = LIFT_TO_TID[main_key]
    second_tid = LIFT_TO_TID[second_key]

    main_wave = waves.get(main_key, _empty_wave_state(main_key, "main"))
    second_wave = waves.get(second_key, _empty_wave_state(second_key, "second"))

    exercises = []

    # ── Main Lift ────────────────────────────────────────────
    main_weight = main_wave["current_weight"]
    # If wave complete, use next_weight
    if main_wave["week_in_wave"] >= 3:
        main_weight = main_wave["next_weight"]
        next_week = 1
    else:
        next_week = main_wave["week_in_wave"] + 1

    scheme = WAVE_SCHEME_MAIN.get(min(next_week, 3), WAVE_SCHEME_MAIN[1])
    main_sets = _build_main_sets(main_weight, scheme["sets"], scheme["reps"])
    exercises.append({
        "exercise_template_id": main_tid,
        "superset_id": None,
        "rest_seconds": 180,
        "notes": f"Wave {main_wave['wave']} W{next_week} — AMRAP last set",
        "sets": main_sets,
    })

    # ── 2nd Lift ─────────────────────────────────────────────
    second_weight = second_wave["current_weight"]
    if second_wave["week_in_wave"] >= 3:
        second_weight = second_wave["next_weight"]
        s_week = 1
    else:
        s_week = second_wave["week_in_wave"] + 1

    s_scheme = WAVE_SCHEME_SECOND.get(min(s_week, 3), WAVE_SCHEME_SECOND[1])
    second_sets = _build_second_sets(second_weight, s_scheme["sets"], s_scheme["reps"])
    exercises.append({
        "exercise_template_id": second_tid,
        "superset_id": None,
        "rest_seconds": 120,
        "notes": f"Straight sets — controlled tempo",
        "sets": second_sets,
    })

    # ── Accessories ──────────────────────────────────────────
    for tid, ex in EXERCISE_DB.items():
        if ex["day"] == day_num and ex["role"] == "accessory":
            exercises.append({
                "exercise_template_id": tid,
                "superset_id": None,
                "rest_seconds": 90,
                "notes": "3-4 x 10-15",
                "sets": _build_accessory_sets(),
            })

    return exercises


def _build_main_sets(weight: float, n_sets: int, reps: int) -> list[dict]:
    """Build main lift sets for Hevy routine. Last set is AMRAP target."""
    sets = []
    for i in range(n_sets):
        sets.append({
            "type": "normal",
            "weight_kg": weight,
            "reps": reps,
        })
    return sets


def _build_second_sets(weight: float, n_sets: int, reps: int) -> list[dict]:
    return [{"type": "normal", "weight_kg": weight, "reps": reps}
            for _ in range(n_sets)]


def _build_accessory_sets(n_sets: int = 3, reps: int = 12) -> list[dict]:
    return [{"type": "normal", "weight_kg": 0, "reps": reps}
            for _ in range(n_sets)]


def update_hevy_routines(df: pd.DataFrame) -> dict:
    """Detect waves from data and update all Hevy routines."""
    waves = detect_waves(df)
    results = {}

    for day_num, routine_id in DAY_ROUTINE_MAP.items():
        if not routine_id:
            results[day_num] = {"status": "skipped", "reason": "no routine_id"}
            continue

        exercises = build_routine_exercises(day_num, waves)
        payload = {"routine": {"exercises": exercises}}

        try:
            url = f"{HEVY_BASE}/routines/{routine_id}"
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                url, data=data, method="PUT",
                headers={"api-key": HEVY_API_KEY, "Content-Type": "application/json"},
            )
            time.sleep(0.35)
            resp = urllib.request.urlopen(req)
            results[day_num] = {"status": "updated", "code": resp.status}
        except Exception as e:
            results[day_num] = {"status": "error", "error": str(e)}

    return results


# ═══════════════════════════════════════════════════════════════════════
#  SUMMARIES & ANALYTICS
# ═══════════════════════════════════════════════════════════════════════

def global_summary(df: pd.DataFrame) -> dict:
    """High-level program summary."""
    if df.empty:
        return {}

    waves = detect_waves(df)
    total_sessions = df["hevy_id"].nunique()
    total_volume = df["volume_kg"].sum()
    date_range = (df["date"].min(), df["date"].max())
    weeks = max(1, (date_range[1] - date_range[0]).days // 7)

    # Per-lift summaries
    lift_summaries = {}
    for lift_key, state in waves.items():
        if state["role"] != "main":
            continue
        lift_summaries[lift_key] = {
            "current_weight": state["current_weight"],
            "wave": state["wave"],
            "week_in_wave": state["week_in_wave"],
            "last_amrap": state["last_amrap"],
            "classification": state["classification"],
            "next_weight": state["next_weight"],
            "total_sessions": state["total_sessions"],
        }

    return {
        "total_sessions": total_sessions,
        "total_volume": round(total_volume),
        "weeks": weeks,
        "avg_sessions_per_week": round(total_sessions / weeks, 1),
        "date_range": date_range,
        "lift_summaries": lift_summaries,
        "waves": waves,
    }


def pr_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build PR table for all tracked lifts."""
    if df.empty:
        return pd.DataFrame()

    tracked = df[df["role"].isin(["main", "second"])].copy()
    if tracked.empty:
        return pd.DataFrame()

    prs = (
        tracked.groupby("lift_key")
        .agg(
            best_e1rm=("e1rm", "max"),
            best_weight=("max_weight", "max"),
            best_reps=("max_reps_at_max", "max"),
            sessions=("hevy_id", "nunique"),
        )
        .reset_index()
    )

    # Add strength level
    prs["level"] = prs.apply(
        lambda r: _strength_level(r["lift_key"], r["best_e1rm"]), axis=1
    )

    return prs.sort_values("best_e1rm", ascending=False)


def _strength_level(lift_key: str, e1rm: float) -> str:
    """Classify lift level based on strength standards."""
    standards = STRENGTH_STANDARDS.get(lift_key)
    if not standards:
        return "—"
    ratio = e1rm / BODYWEIGHT
    if ratio >= standards["elite"]:
        return "Elite"
    elif ratio >= standards["advanced"]:
        return "Advanced"
    elif ratio >= standards["intermediate"]:
        return "Intermediate"
    elif ratio >= standards["beginner"]:
        return "Beginner"
    return "Untrained"


def lift_progression(df: pd.DataFrame) -> pd.DataFrame:
    """Build progression timeline for all main lifts."""
    if df.empty:
        return pd.DataFrame()

    main_df = df[df["role"] == "main"].copy()
    if main_df.empty:
        return pd.DataFrame()

    return (
        main_df.groupby(["date", "lift_key"])
        .agg(
            weight=("max_weight", "max"),
            e1rm=("e1rm", "max"),
            amrap=("amrap_reps", "first"),
            n_sets=("n_sets", "first"),
            volume=("volume_kg", "sum"),
        )
        .reset_index()
        .sort_values(["lift_key", "date"])
    )
