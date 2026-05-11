{{ config(materialized='table') }}

-- Volume anomaly detection per ticker
-- Flags days where volume is significantly above the 5-day average
-- High volume before earnings can signal informed trading activity
with base as (
    select
        ticker,
        trade_date,
        volume,
        close_price,
        price_change_pct,
        day_direction,

        -- 5-day average volume for this ticker
        -- excludes current day so we're comparing against prior behavior
        avg(volume) over (
            partition by ticker
            order by trade_date
            rows between 5 preceding and 1 preceding
        ) as avg_volume_5d,

        -- How many days of data we have for context
        count(*) over (partition by ticker) as total_days

    from {{ ref('mrt_market_summary') }}
),

anomalies as (
    select
        ticker,
        trade_date,
        close_price,
        price_change_pct,
        day_direction,
        volume,
        round(avg_volume_5d, 0) as avg_volume_5d,

        -- Volume ratio: how much higher than average is today's volume?
        round(volume / nullif(avg_volume_5d, 0), 2) as volume_ratio,

        -- Flag as anomaly if volume is 50% above the 5-day average
        case
            when volume > avg_volume_5d * 1.5 then true
            else false
        end as is_volume_anomaly,

        -- Severity of the anomaly
        case
            when volume > avg_volume_5d * 3.0 then 'EXTREME'
            when volume > avg_volume_5d * 2.0 then 'HIGH'
            when volume > avg_volume_5d * 1.5 then 'ELEVATED'
            else 'NORMAL'
        end as anomaly_severity

    from base
    where avg_volume_5d is not null  -- skip days without enough history
)

select * from anomalies
order by ticker, trade_date