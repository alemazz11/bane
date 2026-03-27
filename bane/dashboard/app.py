"""BANE Dashboard — Streamlit visualization of attack evolution."""

import sqlite3
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(
    page_title="BANE Dashboard",
    page_icon="🔥",
    layout="wide",
)

DB_PATH = Path(__file__).parent.parent.parent / "data" / "attacks.db"


@st.cache_data(ttl=30)
def load_data():
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    df = pd.read_sql("SELECT * FROM attacks ORDER BY timestamp", conn)
    conn.close()
    if "timestamp" in df.columns and not df.empty:
        df["time"] = pd.to_datetime(df["timestamp"], unit="s", errors="coerce")
    return df


def get_lineage(df, attack_id):
    """Walk parent chain for a single attack."""
    chain = []
    current = attack_id
    ids_in_df = set(df["id"].values)
    while current and current in ids_in_df:
        row = df[df["id"] == current].iloc[0]
        chain.append(row)
        current = row.get("parent_id")
    chain.reverse()
    return chain


# ── Header ──────────────────────────────────────────────────────
st.title("🔥 BANE — Attack Evolution Dashboard")

df = load_data()

if df.empty:
    st.warning("No attacks yet. Run `python run.py` to start BANE.")
    st.stop()

# ── KPI Row ─────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
total = len(df)
successes = int(df["success"].sum())
c1.metric("Total Attacks", total)
c2.metric("Successes", successes)
c3.metric("Success Rate", f"{df['success'].mean():.1%}")
c4.metric("Avg Score", f"{df['success_score'].mean():.3f}")
c5.metric("Max Generation", int(df["generation"].max()))

st.divider()

# ── Score Evolution ─────────────────────────────────────────────
st.subheader("Score Evolution")

df_sorted = df.sort_values("timestamp").reset_index(drop=True)
df_sorted["rolling"] = df_sorted["success_score"].rolling(window=20, min_periods=1).mean()

fig_evo = go.Figure()
fig_evo.add_trace(go.Scatter(
    x=df_sorted.index, y=df_sorted["success_score"],
    mode="markers", name="Individual",
    marker=dict(size=4, color=df_sorted["success_score"],
                colorscale="RdYlGn", opacity=0.5),
))
fig_evo.add_trace(go.Scatter(
    x=df_sorted.index, y=df_sorted["rolling"],
    mode="lines", name="Rolling Avg (20)",
    line=dict(color="white", width=2),
))
fig_evo.update_layout(
    xaxis_title="Attack #", yaxis_title="Score",
    template="plotly_dark", height=400,
)
st.plotly_chart(fig_evo, use_container_width=True)

# ── Two columns: Category + Strategy ───────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Success by Category")
    cat = df.groupby("category").agg(
        avg_score=("success_score", "mean"),
        count=("id", "count"),
        successes=("success", "sum"),
    ).reset_index().sort_values("avg_score", ascending=False)

    fig_cat = px.bar(
        cat, x="category", y="avg_score",
        color="avg_score", color_continuous_scale="RdYlGn",
        text="count", template="plotly_dark",
    )
    fig_cat.update_layout(height=350)
    st.plotly_chart(fig_cat, use_container_width=True)

with col_right:
    st.subheader("Success by Strategy")
    strat = df.groupby("mutation_type").agg(
        avg_score=("success_score", "mean"),
        count=("id", "count"),
        successes=("success", "sum"),
    ).reset_index().sort_values("avg_score", ascending=False)

    fig_strat = px.bar(
        strat, x="mutation_type", y="avg_score",
        color="avg_score", color_continuous_scale="RdYlGn",
        text="count", template="plotly_dark",
    )
    fig_strat.update_layout(height=350)
    st.plotly_chart(fig_strat, use_container_width=True)

# ── Generation Depth ────────────────────────────────────────────
st.subheader("Evolution Depth")
gen = df.groupby("generation").agg(
    avg_score=("success_score", "mean"),
    count=("id", "count"),
).reset_index()

fig_gen = px.bar(
    gen, x="generation", y="avg_score",
    color="avg_score", color_continuous_scale="RdYlGn",
    text="count", template="plotly_dark",
)
fig_gen.update_layout(height=300)
st.plotly_chart(fig_gen, use_container_width=True)

# ── Top Breakthroughs ──────────────────────────────────────────
st.subheader("🏆 Top Breakthroughs")
breakthroughs = df[df["success"] == 1].sort_values("success_score", ascending=False)

if breakthroughs.empty:
    st.info("No breakthroughs yet.")
else:
    for _, row in breakthroughs.head(10).iterrows():
        with st.expander(
            f"Score: {row['success_score']:.2f} | "
            f"Gen: {row['generation']} | "
            f"{row['category']} -> {row['mutation_type']}"
        ):
            st.markdown(f"**Attack:**\n```\n{row['text'][:500]}\n```")
            st.markdown(f"**Target Response:**\n```\n{row['target_response'][:500]}\n```")
            if row.get("reasoning"):
                st.markdown(f"**Judge:** {row['reasoning']}")

            # Lineage
            lineage = get_lineage(df, row["id"])
            if len(lineage) > 1:
                chain_str = " -> ".join(
                    f"gen{int(a['generation'])}:{a['mutation_type']}({a['success_score']:.1f})"
                    for a in lineage
                )
                st.markdown(f"**Evolution:** `{chain_str}`")

            # Analyzer insights
            analysis_raw = row.get("analysis", "{}")
            if analysis_raw and analysis_raw != "{}":
                try:
                    analysis = json.loads(analysis_raw) if isinstance(analysis_raw, str) else analysis_raw
                    if analysis:
                        st.markdown(
                            f"**Analysis:** Technique: {analysis.get('key_technique', '?')} | "
                            f"Pattern: {analysis.get('pattern', '?')} | "
                            f"Suggested: {analysis.get('suggested_next_mutation', '?')}"
                        )
                except (json.JSONDecodeError, TypeError):
                    pass

# ── Full Attack Log ────────────────────────────────────────────
st.subheader("Full Attack Log")

# Filters
filter_col1, filter_col2, filter_col3 = st.columns(3)
with filter_col1:
    cat_filter = st.multiselect("Category", options=sorted(df["category"].dropna().unique()))
with filter_col2:
    strat_filter = st.multiselect("Strategy", options=sorted(df["mutation_type"].dropna().unique()))
with filter_col3:
    score_range = st.slider("Score Range", 0.0, 1.0, (0.0, 1.0), step=0.1)

filtered = df.copy()
if cat_filter:
    filtered = filtered[filtered["category"].isin(cat_filter)]
if strat_filter:
    filtered = filtered[filtered["mutation_type"].isin(strat_filter)]
filtered = filtered[
    (filtered["success_score"] >= score_range[0]) &
    (filtered["success_score"] <= score_range[1])
]

st.dataframe(
    filtered[["id", "category", "mutation_type", "generation",
              "success_score", "success", "defense_triggered"]].tail(100),
    use_container_width=True,
)

st.caption(f"Showing {len(filtered)} of {total} attacks")
