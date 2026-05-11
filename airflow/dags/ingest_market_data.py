from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import subprocess
import sys
import boto3
import time

default_args = {
    'owner': 'finflow',
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def run_ingestion():
    """Pull OHLCV data from Polygon.io and land it in S3 bronze layer."""
    subprocess.run(
        [sys.executable, '/opt/airflow/scripts/ingest_market_data.py'],
        check=True
    )

def run_validation():
    """Run Great Expectations checks on bronze data. Fails pipeline if data is bad."""
    subprocess.run(
        [sys.executable, '/opt/airflow/quality/validate_bronze.py'],
        check=True
    )

def run_glue_crawler():
    """Trigger the Glue crawler to refresh the bronze catalog schema."""
    client = boto3.client('glue', region_name='us-east-1')

    # Check if crawler is already running — if so just wait for it
    response = client.get_crawler(Name='finflow-market-data-crawler')
    state = response['Crawler']['State']

    if state == 'READY':
        # Only start it if it's not already running
        client.start_crawler(Name='finflow-market-data-crawler')
        print("Crawler started.")
    else:
        print(f"Crawler already in state: {state} — waiting for it to finish.")

    # Wait for crawler to finish
    while True:
        response = client.get_crawler(Name='finflow-market-data-crawler')
        state = response['Crawler']['State']
        if state == 'READY':
            break
        print(f"Crawler state: {state} — waiting...")
        time.sleep(10)

    print("Glue crawler finished successfully.")

with DAG(
    dag_id='finflow_daily_pipeline',
    default_args=default_args,
    description='Full FinFlow daily pipeline: ingest → validate → catalog → transform',
    schedule='0 6 * * 1-5',        # runs Monday-Friday at 6am
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['finflow', 'daily'],
) as dag:

    # Task 1: pull fresh market data from Polygon.io into S3 bronze
    ingest = PythonOperator(
        task_id='ingest_market_data',
        python_callable=run_ingestion,
    )

    # Task 2: validate bronze data with Great Expectations
    # if this fails, the rest of the pipeline stops
    validate = PythonOperator(
        task_id='validate_bronze',
        python_callable=run_validation,
    )

    # Task 3: refresh Glue catalog so Redshift Spectrum sees new files
    crawl = PythonOperator(
        task_id='run_glue_crawler',
        python_callable=run_glue_crawler,
    )

    # Task 4: run dbt staging model to clean and type the bronze data
    dbt_staging = BashOperator(
        task_id='dbt_staging',
        bash_command='cd /opt/airflow/dbt && dbt run --profiles-dir /opt/airflow/dbt --select stg_market_data',
    )

    # Task 5: run dbt mart models to produce gold layer analytics
    dbt_marts = BashOperator(
        task_id='dbt_marts',
        bash_command='cd /opt/airflow/dbt && dbt run --profiles-dir /opt/airflow/dbt --select mrt_market_summary mrt_volume_anomaly',
    )

    # Pipeline order: each task only runs if the previous one succeeded
    ingest >> validate >> crawl >> dbt_staging >> dbt_marts