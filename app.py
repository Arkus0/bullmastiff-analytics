"""
Baby Mastiff — Streamlit Dashboard
"""
import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="🐕 Baby Mastiff", page_icon="🐕", layout="wide")

from src.analytics import (
    fetch_bm_workouts, workouts_to_dataframe, detect_waves,
    global_summary, pr_table, lift_progression,
)
from src.config import (
    DAY_CONFIG, BODYWEIGHT, STRENGTH_STANDARDS,
    AMRAP_THRESHOLDS, classify_amrap,
)


@st.cache_data(ttl=300)
def load_data():
    workouts = fetch_bm_workouts()
    if not workouts:
        return pd.DataFrame(), {}
    df = workouts_to_dataframe(workouts)
    waves = detect_waves(df)
    return df, waves


def main():
    st.title("🐕 Baby Mastiff Analytics")
    st.caption("Bromley Baby Bully · 5-Day · Wave Progression")

    if not os.environ.get("HEVY_API_KEY"):
        st.error("Set HEVY_API_KEY environment variable")
        return

    df, waves = load_data()

    if df.empty:
        st.warning("No Baby Mastiff workouts found. Start training!")
        return

    summary = global_summary(df)

    # ── Overview ─────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sesiones", summary["total_sessions"])
    c2.metric("Semanas", summary["weeks"])
    c3.metric("Sesiones/semana", summary["avg_sessions_per_week"])
    c4.metric("Volumen total", f"{summary['total_volume']:,.0f} kg")

    st.divider()

    # ── Wave Status ──────────────────────────────────────────
    st.subheader("🌊 Estado de Ondas")

    cols = st.columns(5)
    for i, (lift_key, state) in enumerate(
        [(k, v) for k, v in waves.items() if v["role"] == "main"]
    ):
        with cols[i % 5]:
            classification = state["classification"] or "—"
            emoji = {"SURGE": "🟢", "ADVANCE": "🟢", "GRIND": "🟡",
                     "STALL": "🔴"}.get(classification, "⚪")

            st.markdown(f"**{emoji} {lift_key.upper()}**")
            st.metric("Peso actual", f"{state['current_weight']} kg")
            st.caption(
                f"Wave {state['wave']} · W{state['week_in_wave']}/3 · "
                f"{state['total_sessions']} sesiones"
            )
            if state["last_amrap"] is not None:
                st.caption(f"AMRAP: {state['last_amrap']} reps → {classification}")
            if state["next_weight"] != state["current_weight"]:
                st.caption(f"→ Siguiente: {state['next_weight']} kg (+{state['next_increment']})")

    st.divider()

    # ── Progression Charts ───────────────────────────────────
    st.subheader("📈 Progresión")

    prog = lift_progression(df)
    if not prog.empty:
        tab1, tab2 = st.tabs(["Peso", "e1RM"])

        with tab1:
            fig = px.line(
                prog, x="date", y="weight", color="lift_key",
                markers=True, title="Peso de trabajo por sesión",
            )
            fig.update_layout(xaxis_title="", yaxis_title="kg")
            st.plotly_chart(fig, use_container_width=True)

        with tab2:
            fig = px.line(
                prog, x="date", y="e1rm", color="lift_key",
                markers=True, title="e1RM estimado por sesión",
            )
            fig.update_layout(xaxis_title="", yaxis_title="kg")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── AMRAP Tracker ────────────────────────────────────────
    st.subheader("💪 AMRAP Tracker")

    amrap_df = df[
        (df["role"] == "main") & (df["amrap_reps"].notna())
    ][["date", "lift_key", "max_weight", "amrap_reps", "e1rm"]].copy()

    if not amrap_df.empty:
        amrap_df["classification"] = amrap_df["amrap_reps"].apply(
            lambda r: classify_amrap(int(r))
        )
        amrap_df["color"] = amrap_df["classification"].map({
            "SURGE": "green", "ADVANCE": "blue",
            "GRIND": "orange", "STALL": "red",
        })

        fig = px.scatter(
            amrap_df, x="date", y="amrap_reps", color="lift_key",
            size="max_weight", hover_data=["classification", "e1rm"],
            title="AMRAP por sesión",
        )
        # Threshold lines
        fig.add_hline(y=15, line_dash="dash", line_color="green",
                      annotation_text="SURGE (≥15)")
        fig.add_hline(y=12, line_dash="dash", line_color="blue",
                      annotation_text="ADVANCE (≥12)")
        fig.add_hline(y=9, line_dash="dash", line_color="orange",
                      annotation_text="GRIND (≥9)")
        fig.update_layout(xaxis_title="", yaxis_title="Reps")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── PR Table ─────────────────────────────────────────────
    st.subheader("🏆 Records Personales")
    prs = pr_table(df)
    if not prs.empty:
        st.dataframe(
            prs.rename(columns={
                "lift_key": "Ejercicio", "best_e1rm": "e1RM",
                "best_weight": "Mejor peso", "best_reps": "Mejor reps",
                "sessions": "Sesiones", "level": "Nivel",
            }),
            hide_index=True,
            use_container_width=True,
        )

    # ── Strength Standards Gauge ─────────────────────────────
    st.subheader("🎯 Niveles de Fuerza")
    for lift_key in ["squat", "bench", "deadlift", "ohp", "pendlay_row"]:
        standards = STRENGTH_STANDARDS.get(lift_key, {})
        if not standards:
            continue
        lift_prs = prs[prs["lift_key"] == lift_key]
        if lift_prs.empty:
            continue
        best = lift_prs.iloc[0]["best_e1rm"]
        ratio = best / BODYWEIGHT
        elite = standards["elite"]

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=ratio,
            title={"text": lift_key.upper()},
            number={"suffix": f"x BW ({best:.0f}kg)"},
            gauge={
                "axis": {"range": [0, elite * 1.1]},
                "steps": [
                    {"range": [0, standards["beginner"]], "color": "#f0f0f0"},
                    {"range": [standards["beginner"], standards["intermediate"]], "color": "#d4edda"},
                    {"range": [standards["intermediate"], standards["advanced"]], "color": "#cce5ff"},
                    {"range": [standards["advanced"], standards["elite"]], "color": "#fff3cd"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75, "value": ratio,
                },
            },
        ))
        fig.update_layout(height=200, margin=dict(t=40, b=0, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

    # ── Volume by Day ────────────────────────────────────────
    st.subheader("📊 Volumen por Día")
    vol_by_day = (
        df.groupby("day_name")["volume_kg"].sum()
        .reset_index()
        .sort_values("volume_kg", ascending=False)
    )
    if not vol_by_day.empty:
        fig = px.bar(vol_by_day, x="day_name", y="volume_kg",
                     title="Volumen total por día de entrenamiento")
        fig.update_layout(xaxis_title="", yaxis_title="kg")
        st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
