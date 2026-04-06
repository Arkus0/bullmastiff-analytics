"""
Baby Mastiff — Sync Orchestrator
Run via GitHub Actions or manually: python -m src.sync
"""
import sys
from datetime import datetime
from src.analytics import (
    fetch_bm_workouts, workouts_to_dataframe, detect_waves,
    global_summary, pr_table, update_hevy_routines,
)
from src.notion import sync_logbook, update_analytics_page
from src.config import NOTION_LOGBOOK_DB


def run_sync(dry_run: bool = False) -> dict:
    print("🐕 Baby Mastiff Sync — Starting...")
    print(f"   {datetime.now().isoformat()}")

    # 1. Fetch
    print("\n📥 Fetching workouts from Hevy...")
    workouts = fetch_bm_workouts()
    print(f"   Found {len(workouts)} Baby Mastiff workouts")

    if not workouts:
        print("   No workouts found. Done.")
        return {"synced": 0, "total": 0}

    # 2. Convert
    df = workouts_to_dataframe(workouts)
    print(f"   {len(df)} exercise entries across {df['hevy_id'].nunique()} sessions")

    # 3. Detect waves
    print("\n🌊 Detecting wave state...")
    waves = detect_waves(df)
    for lift_key, state in waves.items():
        if state["role"] == "main":
            status = state["classification"] or "IN_PROGRESS"
            print(f"   {lift_key.upper()}: Wave {state['wave']} W{state['week_in_wave']} "
                  f"@ {state['current_weight']}kg — {status}")

    # 4. Sync to Notion
    synced = 0
    if not dry_run and NOTION_LOGBOOK_DB:
        print("\n📤 Syncing to Notion logbook...")
        synced = sync_logbook(df, NOTION_LOGBOOK_DB)
        print(f"   Synced {synced} new entries")

        print("\n📊 Updating analytics page...")
        update_analytics_page(df, waves)
        print("   Done")
    elif dry_run:
        print("\n🏜️ Dry run — skipping Notion writes")

    # 5. Update Hevy routines
    if not dry_run:
        print("\n🔄 Updating Hevy routines...")
        results = update_hevy_routines(df)
        for day, r in results.items():
            print(f"   D{day}: {r['status']}")

    # 6. Summary
    summary = global_summary(df)
    prs = pr_table(df)
    print(f"\n✅ Sync complete — {summary.get('total_sessions', 0)} total sessions, "
          f"{synced} new entries synced")

    return {"synced": synced, "total": len(df)}


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    run_sync(dry_run=dry)
