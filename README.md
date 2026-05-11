# FinFlow

A batch financial data pipeline on AWS. Pulls real equity market data from Polygon.io daily, runs it through a medallion architecture (S3 → Redshift Serverless), transforms it with dbt, and surfaces volume anomaly signals in a Streamlit dashboard.

Live dashboard: https://finflow-qd9lds4ulpe4gvka8ptkmy.streamlit.app

---

## What it does

Every weekday at 6am ET, a GitHub Actions workflow:

1. Pulls OHLCV data for AAPL, MSFT, JPM, and GS from Polygon.io and lands raw JSON in S3 (bronze layer)
2. Runs Great Expectations checks on the bronze data — null fields, negative prices, empty result sets. If any check fails, the pipeline stops
3. Triggers an AWS Glue crawler to refresh the catalog schema
4. Runs three dbt models that clean, type, and reshape the data into silver and gold tables in Redshift Serverless
5. The Streamlit dashboard reads from the gold layer and updates automatically

The gold layer answers a specific question: which stocks are showing pre-earnings volume anomalies consistent with informed trading? Days where volume is 1.5x or more above the 5-day average get flagged and graded (ELEVATED, HIGH, EXTREME).

---

## Stack

| Layer | Tool |
|---|---|
| Ingestion | Python + Polygon.io API |
| Raw storage | AWS S3 (bronze/silver/gold prefixes) |
| Schema catalog | AWS Glue |
| Warehouse | Redshift Serverless |
| Transformation | dbt |
| Orchestration | Apache Airflow (Docker) + GitHub Actions |
| Data quality | Great Expectations |
| Infrastructure | Terraform |
| Dashboard | Streamlit |

---

## Architecture

```
Polygon.io API
      |
      v
Python ingestion script
      |
      v
S3 bronze layer (raw JSON, partitioned by ticker/date)
      |
      v
Great Expectations validation
      |
      v
AWS Glue crawler (schema inference)
      |
      v
Redshift Spectrum (external tables over S3)
      |
      v
dbt models
  stg_market_data      -- clean, typed rows from bronze
  mrt_market_summary   -- daily price movement and momentum signals
  mrt_volume_anomaly   -- volume spike detection vs 5-day average
      |
      v
Streamlit dashboard (gold layer queries)
```

---

## dbt models

**staging/stg_market_data**
Reads raw JSON from S3 via Redshift Spectrum. Unnests the results array, renames single-letter fields to readable column names, converts Unix millisecond timestamps to proper dates.

**marts/mrt_market_summary**
Daily summary per ticker: open, high, low, close, volume, VWAP, price change in dollars and percent, intraday range, and a day direction flag (UP/DOWN/FLAT).

**marts/mrt_volume_anomaly**
Computes a 5-day rolling average volume using a window function, calculates a volume ratio for each day, and flags anomalies at three severity thresholds. Days with a ratio above 1.5x are flagged ELEVATED, above 2.0x are HIGH, above 3.0x are EXTREME.

---

## Data quality

Great Expectations runs at the bronze→silver boundary before any data reaches the warehouse. The suite checks:

- ticker, open, close, volume, timestamp are non-null
- status field equals "OK" (Polygon returns this on valid responses)
- open price and volume are positive
- result set has at least one row

A failed check exits with code 1, which stops the GitHub Actions workflow and marks the run failed. Bad data never reaches Redshift.

---

## Infrastructure

Everything is provisioned with Terraform: the S3 bucket, Glue database and crawler, IAM roles for Glue and Redshift, the Redshift Serverless namespace and workgroup.

Redshift Serverless was the right call for this project. Classic Redshift charges by the hour whether you're running queries or not. Serverless charges per RPU-hour of actual query time, which works out to a few dollars a month during active development and roughly zero when idle.

---

## Running locally

**Requirements:** Python 3.10+, AWS CLI configured, Docker Desktop

```bash
git clone https://github.com/sagarvrma/finflow.git
cd finflow
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your credentials:

```
POLYGON_API_KEY=your_key
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_key
AWS_DEFAULT_REGION=us-east-1
REDSHIFT_HOST=your_workgroup_endpoint
REDSHIFT_PASSWORD=your_password
```

Run the ingestion script:

```bash
python ingestion/ingest_market_data.py
```

Validate bronze data:

```bash
python quality/validate_bronze.py
```

Run dbt:

```bash
cd finflow_dbt
dbt run
```

Start Airflow:

```bash
cd airflow
docker compose up -d
```

Start the dashboard:

```bash
streamlit run dashboard/app.py
```

---

## Why these tickers

AAPL and MSFT cover large-cap tech. JPM and GS cover major banks. The combination gives the volume anomaly model two sectors to compare against, which matters because tech and financials have different baseline volume profiles and different earnings calendars. A spike in GS volume the week before Goldman reports earnings reads differently than the same spike in AAPL.

---

## Project context

This project was built as a portfolio piece targeting data engineering roles at financial institutions. It covers the parts of the DE stack that don't show up in streaming-focused projects: batch ingestion, warehouse modeling, IaC, and data quality enforcement. A separate project (dark-pool-detector) handles the Kafka/Spark/streaming side of the same domain.

---

## Cost

Running this project costs roughly $3-8/month in AWS charges, almost entirely from Redshift Serverless query time. S3, Glue, and GitHub Actions are effectively free at this usage level.