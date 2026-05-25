"""
Bullmastiff — Analytics & Autoprogression

Phases: Base (3 waves × 3 weeks) + Peak (3 waves × 3 weeks) = 18 weeks.
Progression:
  Main:      1% of 1RM per rep above baseline on the AMRAP set.
  Variation: step loading (sets +1/week within wave, reset on new wave).
  Accessories: step loading (sets +1/week, 2 sub-waves cycling).

Update flow: fetch workouts → detect position → build exercises → PUT routines.
"""
import os, time, json, urllib.request
from datetime import datetime

import pandas as pd

from src.config import (
    DAY_CONFIG, DAY_ROUTINE_MAP, LIFT_TO_TID, TID_TO_LIFT,
    ONE_RM, BASE_MAIN, PEAK_MAIN, BASE_VAR, PEAK_VAR,
    MAIN_LIFTS, VAR_LIFTS, MAIN_TO_VAR, BODYWEIGHT, STRENGTH_STANDARDS,
    round_to_plate, get_variation_1rm, get_acc_prescription,
)

HEVY_API_KEY = os.environ.get("HEVY_API_KEY", "")
HEVY_BASE    = "https://api.hevyapp.com/v1"


# ═══════════════════════════════════════════════════════════════════════
#  HEVY CLIENT
# ═══════════════════════════════════════════════════════════════════════

def _hevy_get(endpoint: str) -> dict:
    time.sleep(0.35)
    req = urllib.request.Request(
        f"{HEVY_BASE}{endpoint}", headers={"api-key": HEVY_API_KEY})
    return json.loads(urllib.request.urlopen(req).read().decode())


def _hevy_put(endpoint: str, body: dict) -> dict:
    time.sleep(0.35)
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{HEVY_BASE}{endpoint}", data=data, method="PUT",
        headers={"api-key": HEVY_API_KEY, "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read().decode())


# ═══════════════════════════════════════════════════════════════════════
#  DATA FETCHING
# ═══════════════════════════════════════════════════════════════════════

def fetch_bull_workouts() -> list[dict]:
    """Fetch all Bullmastiff workouts (title starts with 'BULL D')."""
    all_wks, page = [], 1
    while True:
        data = _hevy_get(f"/workouts?page={page}&pageSize=10")
        wks  = data.get("workouts", [])
        if not wks:
            break
        for w in wks:
            if w.get("title", "").startswith("BULL D"):
                all_wks.append(w)
        if page >= data.get("page_count", 1):
            break
        page += 1
    return all_wks


def workouts_to_dataframe(workouts: list[dict]) -> pd.DataFrame:
    """Flatten raw Hevy workouts into one row per exercise per session."""
    rows = []
    for w in workouts:
        date  = w["start_time"][:10]
        title = w["title"]
        hevy_id = w["id"]

        import re
        m = re.search(r"D(\d)", title)
        day_num = int(m.group(1)) if m else None

        start = datetime.fromisoformat(w["start_time"].replace("Z", "+00:00"))
        end   = datetime.fromisoformat(w["end_time"].replace("Z", "+00:00"))
        dur   = round((end - start).total_seconds() / 60)

        for ex in w.get("exercises", []):
            tid  = ex.get("exercise_template_id", "")
            sets = [s for s in ex.get("sets", [])
                    if s.get("type") in ("normal", "failure", None)]
            if not sets:
                sets = ex.get("sets", [])

            weights   = [s.get("weight_kg", 0) or 0 for s in sets]
            reps_list = [s.get("reps", 0)       or 0 for s in sets]
            volume    = sum(w_ * r for w_, r in zip(weights, reps_list))

            max_w = max(weights) if weights else 0
            max_r = max((r for w_, r in zip(weights, reps_list) if w_ == max_w), default=0)
            e1rm  = round(max_w * (1 + max_r / 30), 1) if max_w > 0 and max_r > 1 else max_w

            lift_key = TID_TO_LIFT.get(tid, "")
            role = ("main" if lift_key in MAIN_LIFTS
                    else "variation" if lift_key in VAR_LIFTS
                    else "accessory")

            amrap_reps = reps_list[-1] if role == "main" and len(reps_list) >= 1 else None

            rows.append({
                "date":       pd.Timestamp(date),
                "hevy_id":    hevy_id,
                "title":      title,
                "day_num":    day_num,
                "duration_min": dur,
                "exercise":   ex.get("title", ""),
                "tid":        tid,
                "lift_key":   lift_key,
                "role":       role,
                "n_sets":     len(sets),
                "reps_list":  reps_list,
                "max_weight": max_w,
                "max_reps":   max_r,
                "volume":     volume,
                "e1rm":       e1rm,
                "amrap_reps": amrap_reps,
            })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["date", "day_num"]).reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════════════════════════════
#  PLAN POSITION
# ═══════════════════════════════════════════════════════════════════════

def get_plan_position(df: pd.DataFrame) -> dict:
    """
    Determine current phase/wave/week from completed sessions per lift.

    Returns:
        {
            "squat": {"phase": "base", "wave": 1, "week": 2,
                      "sessions_done": 2, "wave_sessions": 2},
            ...
        }
    3 weeks per wave, 3 waves per phase = 9 sessions per phase per lift.
    Sessions are counted per-lift (each day = 1 session for that lift).
    """
    positions = {}
    for main_key in MAIN_LIFTS:
        if df.empty:
            n = 0
        else:
            n = df[(df["lift_key"] == main_key) & (df["role"] == "main")]["hevy_id"].nunique()

        # 9 sessions per phase (3 waves × 3 weeks)
        if n < 9:
            phase = "base"
            wave  = (n // 3) + 1
            week  = (n % 3) + 1
        else:
            peak_n = n - 9
            phase  = "peak"
            wave   = (peak_n // 3) + 1
            week   = (peak_n % 3) + 1
            if wave > 3:
                wave, week = 3, 3   # clamp at peak wave 3 week 3

        positions[main_key] = {
            "phase":          phase,
            "wave":           wave,
            "week":           week,
            "sessions_done":  n,
            "wave_sessions":  n % 3 if n > 0 else 0,
        }
    return positions


# ═══════════════════════════════════════════════════════════════════════
#  WEIGHT COMPUTATION
# ═══════════════════════════════════════════════════════════════════════

def compute_main_weight(lift_key: str, df: pd.DataFrame,
                        phase: str, wave: int) -> float:
    """
    Current working weight for a main lift.

    Logic:
    - Start of program: prescribed % × 1RM.
    - Each week: weight increases by (amrap_reps_above_baseline × 1% of 1RM).
      Accumulated over the wave until reset at new wave start.
    """
    one_rm = ONE_RM[lift_key]
    pct_map = BASE_MAIN if phase == "base" else PEAK_MAIN
    baseline_reps = pct_map[wave]["reps"]
    start_pct     = pct_map[wave]["pct"]
    start_w       = round_to_plate(one_rm * start_pct)

    if df.empty:
        return start_w

    main_df = (df[(df["lift_key"] == lift_key) & (df["role"] == "main")]
               .sort_values("date").reset_index(drop=True))
    if main_df.empty:
        return start_w

    # Sessions in current phase+wave
    phase_offset = 0 if phase == "base" else 9
    wave_offset  = phase_offset + (wave - 1) * 3
    # All sessions from wave_offset onward
    wave_sessions = main_df.iloc[wave_offset:]

    # Accumulate weight from start_w, adding 1%1RM per extra rep each week
    w = start_w
    for _, row in wave_sessions.iterrows():
        amrap = row["amrap_reps"]
        if amrap is None:
            continue
        extra = max(0, int(amrap) - baseline_reps)
        increment = round_to_plate(extra * one_rm * 0.01)
        w = round_to_plate(w + increment)

    return w


def compute_variation_weight(main_key: str, var_key: str,
                              df: pd.DataFrame, phase: str, wave: int) -> float:
    """
    Variation weight. Fixed within a wave (based on variation 1RM).
    Increases by standard increment on new wave.
    """
    var_1rm = get_variation_1rm(main_key)
    pct_map = BASE_VAR if phase == "base" else PEAK_VAR
    pct     = pct_map[wave]["pct"]
    w       = round_to_plate(var_1rm * pct)

    # Override with last recorded variation weight if available
    if not df.empty:
        var_df = (df[(df["lift_key"] == var_key) & (df["role"] == "variation")]
                  .sort_values("date"))
        if not var_df.empty:
            # Use last actual weight (variation weight is constant within wave,
            # we only update at wave transitions via this function)
            w = var_df["max_weight"].iloc[-1]

    return w


# ═══════════════════════════════════════════════════════════════════════
#  ROUTINE BUILDER
# ═══════════════════════════════════════════════════════════════════════

def _normal_sets(weight: float, n: int, reps: int) -> list[dict]:
    return [{"type": "normal", "weight_kg": float(weight), "reps": reps}
            for _ in range(n)]


def _acc_sets(n: int, reps: int) -> list[dict]:
    return [{"type": "normal", "weight_kg": 0.0, "reps": reps}
            for _ in range(n)]


def build_routine_exercises(day_num: int, df: pd.DataFrame,
                             positions: dict) -> list[dict]:
    """
    Build Hevy exercise list for one routine.

    Main + variation weights computed from history + progression rules.
    Accessories use step loading sets (weight = 0, fill in manually).
    """
    cfg      = DAY_CONFIG[day_num]
    main_key = cfg["main_key"]
    var_key  = cfg["var_key"]
    pos      = positions[main_key]
    phase, wave, week = pos["phase"], pos["wave"], pos["week"]

    # ── Main lift ────────────────────────────────────────────────────
    main_w = compute_main_weight(main_key, df, phase, wave)
    pct_map = BASE_MAIN if phase == "base" else PEAK_MAIN
    baseline_reps = pct_map[wave]["reps"]

    if phase == "base":
        n_main_sets = 4
    else:  # peak: sets decrease by week
        n_main_sets = PEAK_MAIN[wave]["sets_by_week"][week]

    phase_tag = f"{phase.capitalize()} W{wave} W{week}"
    main_ex = {
        "exercise_template_id": LIFT_TO_TID[main_key],
        "superset_id": None,
        "rest_seconds": 300 if main_key == "deadlift" else 240,
        "notes": f"{n_main_sets}x{baseline_reps}+ | AMRAP last | +1%1RM/rep | {phase_tag}",
        "sets": _normal_sets(main_w, n_main_sets, baseline_reps),
    }

    # ── Variation ────────────────────────────────────────────────────
    var_w = compute_variation_weight(main_key, var_key, df, phase, wave)
    if phase == "base":
        var_reps    = BASE_VAR[wave]["reps"]
        var_n_sets  = week + 2   # week1→3, week2→4, week3→5
        var_note    = f"{var_n_sets}x{var_reps} @{int(BASE_VAR[wave]['pct']*100)}% | step loading"
    else:
        var_reps   = PEAK_VAR[wave]["reps"]
        var_n_sets = PEAK_VAR[wave]["sets_by_week"][week]
        var_note   = f"{var_n_sets}x{var_reps} @{int(PEAK_VAR[wave]['pct']*100)}% | sets decrease"

    var_ex = {
        "exercise_template_id": LIFT_TO_TID[var_key],
        "superset_id": None,
        "rest_seconds": 120,
        "notes": var_note,
        "sets": _normal_sets(var_w, var_n_sets, var_reps),
    }

    # ── Accessories ──────────────────────────────────────────────────
    acc_presc = get_acc_prescription(phase, wave, week)
    exercises = [main_ex, var_ex]

    for acc_key in cfg["acc_A"]:
        if acc_key not in LIFT_TO_TID:
            continue
        n, r = acc_presc["A"]["sets"], acc_presc["A"]["reps"]
        exercises.append({
            "exercise_template_id": LIFT_TO_TID[acc_key],
            "superset_id": None,
            "rest_seconds": 90,
            "notes": f"A | {n}x{r} (step loading)",
            "sets": _acc_sets(n, r),
        })

    for acc_key in cfg["acc_B"]:
        if acc_key not in LIFT_TO_TID:
            continue
        n, r = acc_presc["B"]["sets"], acc_presc["B"]["reps"]
        exercises.append({
            "exercise_template_id": LIFT_TO_TID[acc_key],
            "superset_id": None,
            "rest_seconds": 60,
            "notes": f"B | {n}x{r} (step loading)",
            "sets": _acc_sets(n, r),
        })

    return exercises


def _routine_title(day_num: int, positions: dict) -> str:
    main_key = DAY_CONFIG[day_num]["main_key"]
    pos = positions[main_key]
    day_name = DAY_CONFIG[day_num]["name"]
    return (f"BULL D{day_num} — {day_name} "
            f"[{pos['phase'].capitalize()} W{pos['wave']} W{pos['week']}]")


def update_hevy_routines(df: pd.DataFrame) -> dict:
    """Detect position from df, rebuild all 4 routines, PUT to Hevy."""
    positions = get_plan_position(df)
    results   = {}

    for day_num, routine_id in DAY_ROUTINE_MAP.items():
        exercises = build_routine_exercises(day_num, df, positions)
        title     = _routine_title(day_num, positions)

        # GET current routine to preserve manual exercise additions
        try:
            current = _hevy_get(f"/routines/{routine_id}")
            curr_exs = current["routine"][0]["exercises"]
            managed_tids = {e["exercise_template_id"] for e in exercises}
            manual = [e for e in curr_exs
                      if e.get("exercise_template_id") not in managed_tids]
            # Strip index fields before PUT
            for e in manual:
                e.pop("index", None)
                for s in e.get("sets", []):
                    s.pop("index", None)
            exercises = exercises + manual
        except Exception:
            pass  # proceed without manual preservation

        payload = {"routine": {"title": title, "notes": "", "exercises": exercises}}
        try:
            _hevy_put(f"/routines/{routine_id}", payload)
            results[day_num] = {"status": "updated", "title": title}
        except Exception as e:
            results[day_num] = {"status": "error", "error": str(e)}

    return results


# ═══════════════════════════════════════════════════════════════════════
#  PROGRESSION PREVIEW (for dashboard / "Hoy te toca")
# ═══════════════════════════════════════════════════════════════════════

def next_session_plan(df: pd.DataFrame, day_num: int) -> dict:
    """
    Preview what the next session should look like for a given day.
    Returns weights, sets, reps for main + variation + accessories.
    """
    positions = get_plan_position(df)
    main_key  = DAY_CONFIG[day_num]["main_key"]
    var_key   = DAY_CONFIG[day_num]["var_key"]
    pos       = positions[main_key]
    phase, wave, week = pos["phase"], pos["wave"], pos["week"]

    main_w = compute_main_weight(main_key, df, phase, wave)
    var_w  = compute_variation_weight(main_key, var_key, df, phase, wave)

    pct_map       = BASE_MAIN if phase == "base" else PEAK_MAIN
    baseline_reps = pct_map[wave]["reps"]

    if phase == "base":
        n_main = 4
    else:
        n_main = PEAK_MAIN[wave]["sets_by_week"].get(week, 1)

    var_reps  = (BASE_VAR[wave]["reps"] if phase == "base"
                 else PEAK_VAR[wave]["reps"])
    var_sets  = ((week + 2) if phase == "base"
                 else PEAK_VAR[wave]["sets_by_week"].get(week, 2))

    acc = get_acc_prescription(phase, wave, week)

    return {
        "day_num":  day_num,
        "day_name": DAY_CONFIG[day_num]["name"],
        "phase":    phase,
        "wave":     wave,
        "week":     week,
        "main": {
            "lift_key": main_key,
            "weight":   main_w,
            "sets":     n_main,
            "reps":     baseline_reps,
            "note":     "AMRAP last set",
        },
        "variation": {
            "lift_key": var_key,
            "weight":   var_w,
            "sets":     var_sets,
            "reps":     var_reps,
            "note":     "Step loading",
        },
        "accessories": acc,
    }


def amrap_classification(reps: int, baseline: int) -> tuple[str, str]:
    """
    Classify AMRAP performance and compute weight jump for next session.
    Returns (category, description).

    +1% 1RM per rep above baseline. Fractional increments rounded to plate.
    """
    extra = reps - baseline
    if extra <= 0:
        return "GRIND", f"No jump — repeat weight"
    cat   = "SURGE" if extra >= 5 else "ADVANCE"
    return cat, f"+{extra} extra reps"


def weight_jump_from_amrap(lift_key: str, amrap_reps: int,
                            baseline_reps: int) -> float:
    """
    How much weight to add after an AMRAP set.
    Formula: extra_reps × (1RM × 1%) rounded to nearest 2kg.
    """
    extra     = max(0, amrap_reps - baseline_reps)
    increment = extra * ONE_RM[lift_key] * 0.01
    return round_to_plate(increment)


# ═══════════════════════════════════════════════════════════════════════
#  ANALYTICS SUMMARIES
# ═══════════════════════════════════════════════════════════════════════

def lift_progression(df: pd.DataFrame) -> pd.DataFrame:
    """Session-by-session weight + e1RM timeline for main lifts."""
    if df.empty:
        return pd.DataFrame()
    return (
        df[df["role"] == "main"]
        .groupby(["date", "lift_key"])
        .agg(weight=("max_weight", "max"), e1rm=("e1rm", "max"),
             amrap=("amrap_reps", "first"), n_sets=("n_sets", "first"))
        .reset_index()
        .sort_values(["lift_key", "date"])
    )


def pr_table(df: pd.DataFrame) -> pd.DataFrame:
    """Best e1RM per lift with strength level classification."""
    if df.empty:
        return pd.DataFrame()
    tracked = df[df["role"].isin(["main", "variation"])]
    if tracked.empty:
        return pd.DataFrame()
    prs = (tracked.groupby("lift_key")
           .agg(best_e1rm=("e1rm","max"), best_weight=("max_weight","max"),
                sessions=("hevy_id","nunique"))
           .reset_index())
    prs["level"] = prs.apply(
        lambda r: _strength_level(r["lift_key"], r["best_e1rm"]), axis=1)
    return prs.sort_values("best_e1rm", ascending=False)


def _strength_level(lift_key: str, e1rm: float) -> str:
    std = STRENGTH_STANDARDS.get(lift_key)
    if not std:
        return "—"
    ratio = e1rm / BODYWEIGHT
    for lvl in ("elite", "advanced", "intermediate", "beginner"):
        if ratio >= std[lvl]:
            return lvl.capitalize()
    return "Untrained"


def global_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {}
    total_sessions = df["hevy_id"].nunique()
    positions = get_plan_position(df)
    return {
        "total_sessions": total_sessions,
        "total_volume":   round(df["volume"].sum()),
        "positions":      positions,
        "prs":            pr_table(df).to_dict("records") if not df.empty else [],
    }
