import streamlit as st
import psycopg2
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
import os

load_dotenv()

# Page config
st.set_page_config(
    page_title="FinFlow Dashboard",
    page_icon="📈",
    layout="wide"
)

# Connection to Redshift
@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=os.getenv("REDSHIFT_HOST"),
        port=5439,
        database="finflow_db",
        user="admin",
        password=os.getenv("REDSHIFT_PASSWORD"),
        sslmode="prefer"
    )

@st.cache_data(ttl=3600)
def load_market_summary():
    conn = get_connection()
    query = """
        SELECT ticker, trade_date, open_price, close_price,
               price_change, price_change_pct, volume, day_direction
        FROM public.mrt_market_summary
        ORDER BY trade_date, ticker
    """
    return pd.read_sql(query, conn)

@st.cache_data(ttl=3600)
def load_volume_anomalies():
    conn = get_connection()
    query = """
        SELECT ticker, trade_date, volume, avg_volume_5d,
               volume_ratio, is_volume_anomaly, anomaly_severity
        FROM public.mrt_volume_anomaly
        ORDER BY trade_date, ticker
    """
    return pd.read_sql(query, conn)

# Load data
st.title("📈 FinFlow — Financial Data Pipeline Dashboard")
st.caption("Real equity market data · Polygon.io → S3 → Redshift · Transformed with dbt")

with st.spinner("Loading data from Redshift..."):
    df_market = load_market_summary()
    df_anomaly = load_volume_anomalies()

# --- Section 1: Market Summary ---
st.header("Market Summary")

# Metric cards for latest day
df_market["trade_date"] = pd.to_datetime(df_market["trade_date"]).dt.date
latest_date = df_market["trade_date"].max()
latest = df_market[df_market["trade_date"] == latest_date].drop_duplicates(subset=["ticker"])

tickers_latest = list(latest.itertuples())
cols = st.columns(len(tickers_latest))
for i, row in enumerate(tickers_latest):
    with cols[i]:
        st.metric(
            label=row.ticker,
            value=f"${row.close_price:.2f}",
            delta=f"{row.price_change_pct:+.2f}%"
        )

# Price chart
st.subheader("Close Price Over Time")
fig_price = px.line(
    df_market,
    x="trade_date",
    y="close_price",
    color="ticker",
    title="Daily Close Price",
    labels={"close_price": "Close Price ($)", "trade_date": "Date"}
)
st.plotly_chart(fig_price, use_container_width=True)

# --- Section 2: Volume Analysis ---
st.header("Volume Anomaly Detection")
st.caption("Flags days where volume is ≥1.5x the 5-day average — a signal of unusual trading activity")

# Color map for severity
severity_colors = {
    "NORMAL": "#4CAF50",
    "ELEVATED": "#FFC107",
    "HIGH": "#FF5722",
    "EXTREME": "#B71C1C"
}

# Volume chart with anomaly highlights
for ticker in df_anomaly["ticker"].unique():
    df_t = df_anomaly[df_anomaly["ticker"] == ticker]

    fig = go.Figure()

    # Bar chart of volume
    fig.add_trace(go.Bar(
        x=df_t["trade_date"],
        y=df_t["volume"],
        name="Volume",
        marker_color=[severity_colors.get(s, "#4CAF50") for s in df_t["anomaly_severity"]],
    ))

    # Line for 5-day average
    fig.add_trace(go.Scatter(
        x=df_t["trade_date"],
        y=df_t["avg_volume_5d"],
        name="5-Day Avg",
        line=dict(color="white", dash="dash"),
    ))

    fig.update_layout(
        title=f"{ticker} — Volume with Anomaly Highlights",
        xaxis_title="Date",
        yaxis_title="Volume",
        legend_title="Legend",
        height=300
    )

    st.plotly_chart(fig, use_container_width=True)

# --- Section 3: Anomaly Table ---
st.header("Flagged Anomalies")
anomalies = df_anomaly[df_anomaly["is_volume_anomaly"] == True].copy()

if anomalies.empty:
    st.info("No anomalies detected in current data window.")
else:
    anomalies["volume_ratio"] = anomalies["volume_ratio"].map("{:.2f}x".format)
    st.dataframe(
        anomalies[["ticker", "trade_date", "volume", "avg_volume_5d", "volume_ratio", "anomaly_severity"]],
        use_container_width=True
    )

st.divider()
st.caption("FinFlow · Built with dbt · Redshift Serverless · Apache Airflow · Great Expectations")