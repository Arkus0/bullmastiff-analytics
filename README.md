# 🐕 Bullmastiff Analytics

**Baby Mastiff** strength program analytics — Bromley's Baby Bully adapted to 5 days with smart wave progression.

## Program Design

Based on Alex Bromley's *Peak Strength* Baby Bully template:

| Day | Main Lift | 2nd Lift | Focus |
|-----|-----------|----------|-------|
| D1 | Squat to Box | RDL | Lower (quad) |
| D2 | Bench Press | BTN Press | Upper push |
| D3 | Deadlift | Zercher Squat | Lower (hinge) |
| D4 | OHP | Close Grip Bench | Upper push |
| D5 | Pendlay Row | Seal Row | Upper pull |

### Wave Progression

Each lift progresses in **3-week waves**:

| Week | Main Lift | 2nd Lift |
|------|-----------|----------|
| 1 | 3×6+ | 3×10 |
| 2 | 4×6+ | 4×10 |
| 3 | 5×6+ | 5×10 |

**"+"** = AMRAP on last set (main lifts only).

After week 3, the AMRAP determines the next wave's weight:

| AMRAP Reps | Classification | Increment |
|------------|---------------|-----------|
| ≥15 | SURGE | Double (4kg upper / 8kg lower) |
| 12–14 | ADVANCE | Standard (2kg upper / 4kg lower) |
| 9–11 | GRIND | Standard (flagged) |
| ≤8 | STALL | Repeat weight |

2nd lifts always use standard increment.

## Stack

- **Hevy** → workout tracking
- **GitHub Actions** → daily sync (00:30 Spain)
- **Notion** → logbook + analytics
- **Streamlit** → dashboard

## Setup

```bash
export HEVY_API_KEY="..."
export NOTION_TOKEN="..."
pip install -r requirements.txt
streamlit run app.py
```

## Sync

```bash
python -m src.sync           # full sync
python -m src.sync --dry-run  # no writes
```
