# Bullmastiff Analytics — AI Context

## Program: Baby Mastiff
Bromley Baby Bully adapted to 5 days. Wave-based progression with AMRAP-driven increments.

## Architecture
- `src/config.py` — Program definition, exercise DB, progression constants
- `src/analytics.py` — Fetch, parse, wave detection, progression, routine updates
- `src/notion.py` — Notion sync (logbook + analytics page)
- `src/sync.py` — Entry point for GitHub Actions
- `app.py` — Streamlit dashboard

## Key IDs
- Hevy API Key: env var `HEVY_API_KEY`
- Notion Token: env var `NOTION_TOKEN`
- Hevy Folder: `2653107`
- Notion Logbook DB: `33acbc49-9cfe-8129-b2f3-e116c5997c11`
- Notion Analytics Page: `33acbc49-9cfe-8116-81e0-d4c57aa119b1`
- Workout title prefix: `BM D` (e.g. "BM D1 Squat / RDL")

## Hevy Routine IDs
- D1 Squat/RDL: `322fe8c0-8e7e-4d71-bc8d-0fb19450f1fc`
- D2 Bench/BTN: `a43f6dbf-1ee3-4f46-87e7-1fe01f2b4749`
- D3 Deadlift/Box Squat: `b508ec84-ff21-4dc2-bc54-6516adab4237`
- D4 Press/CG Bench: `55852c04-1f11-4419-9d89-addc8e0004b9`
- D5 Row/Seal Row: `223f783f-04d2-441e-bb53-e3875dd96244`

## Exercise Template IDs
- Squat to Box: `38FC1AB9`
- Bench Press: `79D0BB3A`
- Deadlift: `C6272009`
- OHP: `7B8D84E8`
- Pendlay Row: `018ADC12`
- RDL: `2B4B7310`
- BTN Press: `883b82a7-8d94-41e9-8efe-644892aa956f`
- Zercher Squat: `40C6A9FC`
- CG Bench: `35B51B87`
- Seal Row: `2c3103bf-bf30-474f-8396-91ad7021b6cf`

## Progression Rules
- Main lifts: 3-week waves (3x6+, 4x6+, 5x6+), AMRAP last set
- AMRAP ≥15 → SURGE (double increment), 12-14 → ADVANCE, 9-11 → GRIND, ≤8 → STALL
- Upper body: +2kg base, Lower body: +4kg base
- 2nd lifts: 3x10, 4x10, 5x10, always standard increment
- All weights rounded to 2kg (1kg per side minimum)

## Development
- Push to main directly, no PRs
- Commits: `feat:`, `fix:`, `refactor:` prefix
- Test with `ast.parse()` + pytest before push
- Hevy PUT: exclude `index` from sets
