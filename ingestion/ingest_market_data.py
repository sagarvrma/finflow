import os
import json
import boto3
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

# Load API key from .env file
load_dotenv()
API_KEY = os.getenv("POLYGON_API_KEY")

# Settings
BUCKET = "finflow-data-sxvarma"
TICKERS = ["AAPL", "MSFT", "JPM", "GS"]
END_DATE = date.today() - timedelta(days=1)  # yesterday
START_DATE = END_DATE - timedelta(days=7)    # last 7 days


def fetch_ohlcv(ticker, start, end):
    """Fetch daily OHLCV data from Polygon.io for a given ticker."""
    url = (
        f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/day"
        f"/{start}/{end}"
        f"?adjusted=true&sort=asc&apiKey={API_KEY}"
    )
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def upload_to_s3(data, ticker, date_str):
    """Upload JSON data to the bronze layer in S3."""
    s3 = boto3.client("s3")
    key = f"bronze/market_data/{ticker}/{date_str}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(data),
        ContentType="application/json"
    )
    print(f"Uploaded {ticker} data to s3://{BUCKET}/{key}")


def main():
    date_str = END_DATE.strftime("%Y-%m-%d")
    print(f"Fetching market data from {START_DATE} to {END_DATE}")

    for ticker in TICKERS:
        print(f"Processing {ticker}...")
        data = fetch_ohlcv(ticker, START_DATE, END_DATE)
        upload_to_s3(data, ticker, date_str)

    print("Done.")


if __name__ == "__main__":
    main()