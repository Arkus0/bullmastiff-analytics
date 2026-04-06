"""
Baby Mastiff — Notion Sync

Sync workout data to Notion logbook database and update analytics page.
"""
import time
import requests
import pandas as pd
from src.config import NOTION_TOKEN, NOTION_LOGBOOK_DB, NOTION_ANALYTICS_PAGE, DAY_CONFIG

BASE_URL = "https://api.notion.com/v1"
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}
RATE_LIMIT_DELAY = 0.35


def _post(endpoint: str, body: dict) -> dict:
    time.sleep(RATE_LIMIT_DELAY)
    r = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=body)
    r.raise_for_status()
    return r.json()


def _patch(endpoint: str, body: dict) -> dict:
    time.sleep(RATE_LIMIT_DELAY)
    r = requests.patch(f"{BASE_URL}{endpoint}", headers=HEADERS, json=body)
    r.raise_for_status()
    return r.json()


def query_database(database_id: str, filter_obj: dict = None) -> list[dict]:
    body = {"page_size": 100}
    if filter_obj:
        body["filter"] = filter_obj
    all_results = []
    has_more = True
    start_cursor = None
    while has_more:
        if start_cursor:
            body["start_cursor"] = start_cursor
        data = _post(f"/databases/{database_id}/query", body)
        all_results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return all_results


def get_synced_hevy_ids(database_id: str) -> set[str]:
    pages = query_database(database_id)
    ids = set()
    for p in pages:
        props = p.get("properties", {})
        rt = props.get("Hevy ID", {}).get("rich_text", [])
        if rt:
            ids.add(rt[0].get("plain_text", ""))
    return ids


def create_logbook_entry(row: pd.Series, database_id: str):
    properties = {
        "Ejercicio": {"title": [{"text": {"content": str(row["exercise"])}}]},
        "Día": {"select": {"name": str(row["day_name"])}},
        "Fecha": {"date": {"start": row["date"].strftime("%Y-%m-%d")}},
        "Series": {"number": int(row["n_sets"])},
        "Reps": {"rich_text": [{"text": {"content": str(row["reps_str"])}}]},
        "Top Set": {"rich_text": [{"text": {"content": str(row["top_set"])}}]},
        "Hevy ID": {"rich_text": [{"text": {"content": str(row["hevy_id"])}}]},
        "Rol": {"select": {"name": str(row["role"])}},
        "PR? 🏆": {"checkbox": bool(row.get("is_pr", False))},
    }
    if row["max_weight"] > 0:
        properties["Peso (kg)"] = {"number": float(row["max_weight"])}
    if row["volume_kg"] > 0:
        properties["Volumen (kg)"] = {"number": float(row["volume_kg"])}
    if row["e1rm"] > 0:
        properties["e1RM"] = {"number": float(row["e1rm"])}
    if row.get("amrap_reps") is not None:
        properties["AMRAP"] = {"number": int(row["amrap_reps"])}
    if row.get("description"):
        properties["Notas"] = {
            "rich_text": [{"text": {"content": str(row["description"])[:2000]}}]
        }

    body = {"parent": {"database_id": database_id}, "properties": properties}
    return _post("/pages", body)


def sync_logbook(df: pd.DataFrame, database_id: str = None) -> int:
    db_id = database_id or NOTION_LOGBOOK_DB
    if not db_id or df.empty:
        return 0

    existing = get_synced_hevy_ids(db_id)
    new_df = df[~df["hevy_id"].isin(existing)]
    if new_df.empty:
        return 0

    new_df = _detect_prs(new_df, df)
    count = 0
    for _, row in new_df.iterrows():
        try:
            create_logbook_entry(row, db_id)
            count += 1
        except Exception as e:
            print(f"  ❌ Error syncing {row['exercise']}: {e}")
    return count


def _detect_prs(new_df: pd.DataFrame, all_df: pd.DataFrame) -> pd.DataFrame:
    new_df = new_df.copy()
    new_df["is_pr"] = False
    existing = all_df[~all_df["hevy_id"].isin(new_df["hevy_id"].unique())]
    hist_max = existing.groupby("exercise_template_id")["e1rm"].max().to_dict() if not existing.empty else {}
    for idx, row in new_df.iterrows():
        if row["e1rm"] > 0:
            prev = hist_max.get(row["exercise_template_id"], 0)
            if row["e1rm"] > prev:
                new_df.loc[idx, "is_pr"] = True
                hist_max[row["exercise_template_id"]] = row["e1rm"]
    return new_df


def update_analytics_page(df: pd.DataFrame, waves: dict):
    """Update the Notion analytics page with current state."""
    if not NOTION_ANALYTICS_PAGE:
        print("  ⚠️ No NOTION_ANALYTICS_PAGE configured, skipping")
        return

    from src.analytics import global_summary, pr_table

    summary = global_summary(df)
    prs = pr_table(df)

    blocks = []
    blocks.append(_heading("🐕 Baby Mastiff — Estado Actual"))
    blocks.append(_text(
        f"📊 {summary.get('total_sessions', 0)} sesiones | "
        f"{summary.get('weeks', 0)} semanas | "
        f"{summary.get('total_volume', 0):,.0f} kg volumen total"
    ))

    blocks.append(_divider())
    blocks.append(_heading("🌊 Estado de Ondas", level=2))

    for lift_key, state in waves.items():
        if state["role"] != "main":
            continue
        emoji = "🟢" if state["classification"] in ("SURGE", "ADVANCE") else \
                "🟡" if state["classification"] == "GRIND" else \
                "🔴" if state["classification"] == "STALL" else "⚪"
        line = (
            f"{emoji} **{lift_key.upper()}**: "
            f"Wave {state['wave']} W{state['week_in_wave']} | "
            f"{state['current_weight']}kg"
        )
        if state["last_amrap"] is not None:
            line += f" | AMRAP: {state['last_amrap']} ({state['classification']})"
        if state["next_weight"] != state["current_weight"]:
            line += f" → {state['next_weight']}kg"
        blocks.append(_text(line))

    # Append blocks (max 100 per request)
    # First clear existing content
    _clear_page(NOTION_ANALYTICS_PAGE)

    for i in range(0, len(blocks), 100):
        chunk = blocks[i:i + 100]
        _patch(f"/blocks/{NOTION_ANALYTICS_PAGE}/children", {"children": chunk})


def _clear_page(page_id: str):
    """Delete all blocks from a page."""
    time.sleep(RATE_LIMIT_DELAY)
    r = requests.get(
        f"{BASE_URL}/blocks/{page_id}/children?page_size=100",
        headers=HEADERS,
    )
    if r.status_code != 200:
        return
    for block in r.json().get("results", []):
        time.sleep(RATE_LIMIT_DELAY)
        requests.delete(f"{BASE_URL}/blocks/{block['id']}", headers=HEADERS)


def _heading(text: str, level: int = 1) -> dict:
    key = f"heading_{level}"
    return {
        "object": "block", "type": key,
        key: {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _text(text: str) -> dict:
    return {
        "object": "block", "type": "paragraph",
        "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]},
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}
