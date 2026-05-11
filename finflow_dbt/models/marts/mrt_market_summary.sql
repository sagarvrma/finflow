{{ config(materialized='table') }}

-- Daily market summary per ticker
-- Reads from the staging model, adds derived metrics
with base as (
    select
        ticker,
        trade_date,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        vwap,
        num_transactions,

        -- Daily price change in dollars
        close_price - open_price as price_change,

        -- Daily price change as a percentage
        round(
            ((close_price - open_price) / nullif(open_price, 0)) * 100,
            2
        ) as price_change_pct,

        -- Intraday range (how volatile was the day)
        high_price - low_price as intraday_range,

        -- Simple momentum signal: was it a up or down day?
        case
            when close_price > open_price then 'UP'
            when close_price < open_price then 'DOWN'
            else 'FLAT'
        end as day_direction

    from {{ ref('stg_market_data') }}
)

select * from base
order by ticker, trade_date