import great_expectations as gx
import boto3
import json
import pandas as pd
from dotenv import load_dotenv
from datetime import date, timedelta

load_dotenv()

def load_bronze_data(ticker: str, date_str: str) -> dict:
    """Load a single bronze JSON file from S3."""
    s3 = boto3.client("s3")
    key = f"bronze/market_data/{ticker}/{date_str}.json"
    response = s3.get_object(Bucket="finflow-data-sxvarma", Key=key)
    return json.loads(response["Body"].read())

def validate_bronze(ticker: str, date_str: str) -> bool:
    """Run Great Expectations checks on a bronze market data file."""

    # Load raw JSON from S3
    raw = load_bronze_data(ticker, date_str)

    # Flatten the nested results array into a list of row dicts
    # Each row = one trading day for this ticker
    records = []
    for result in raw.get("results", []):
        records.append({
            "ticker":    raw.get("ticker"),
            "status":    raw.get("status"),
            "count":     raw.get("count"),
            "open":      result.get("o"),
            "high":      result.get("h"),
            "low":       result.get("l"),
            "close":     result.get("c"),
            "volume":    result.get("v"),
            "timestamp": result.get("t"),
        })

    # Convert to a pandas DataFrame so GX can validate it
    df = pd.DataFrame(records)

    # Ephemeral context = no files written to disk, runs in memory only
    context = gx.get_context(mode="ephemeral")

    # Add a pandas data source and asset
    ds = context.data_sources.add_pandas("bronze_ds")
    da = ds.add_dataframe_asset("market_data_asset")

    # A batch definition tells GX how to slice the data — here we use the whole DataFrame
    batch_definition = da.add_batch_definition_whole_dataframe("batch")

    # An expectation suite is a named collection of rules (expectations)
    suite = context.suites.add(gx.ExpectationSuite(name="bronze_market_data"))

    # Rule: key columns must never be null
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="ticker"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="open"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="close"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="volume"))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="timestamp"))

    # Rule: Polygon always returns status "OK" on success — anything else means a bad response
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeInSet(
        column="status", value_set=["OK"]
    ))

    # Rule: prices and volume must be positive numbers
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(
        column="open", min_value=0
    ))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeBetween(
        column="volume", min_value=0
    ))

    # Rule: we must have at least 1 row — empty results means something went wrong
    suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=1))

    # A validation definition links a batch definition to a suite
    vd = context.validation_definitions.add(
        gx.ValidationDefinition(name="bronze_validation", data=batch_definition, suite=suite)
    )

    # Run the validation, passing the actual DataFrame at runtime
    results = vd.run(batch_parameters={"dataframe": df})

    # Print a summary of each check
    print(f"\n{'='*50}")
    print(f"Validation results for {ticker} on {date_str}")
    print(f"{'='*50}")
    print(f"Success: {results.success}")
    for result in results.results:
        status = "✓" if result.success else "✗"
        print(f"  {status} {result.expectation_config.type}")

    return results.success


if __name__ == "__main__":
    # Use yesterday's date since markets close before end of day
    date_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    tickers = ["AAPL", "MSFT", "JPM", "GS"]

    all_passed = True
    for ticker in tickers:
        passed = validate_bronze(ticker, date_str)
        if not passed:
            all_passed = False

    # Exit code 1 halts the pipeline in Airflow
    if all_passed:
        print("\n✓ All validations passed. Pipeline can proceed.")
    else:
        print("\n✗ Validation failures detected. Pipeline halted.")
        exit(1)