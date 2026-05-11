{{ config(materialized='table') }}

select
    s.ticker,
    result.o::float       as open_price,
    result.h::float       as high_price,
    result.l::float       as low_price,
    result.c::float       as close_price,
    result.v::float       as volume,
    result.vw::float      as vwap,
    result.n::integer     as num_transactions,
    dateadd(ms, result.t::bigint, '1970-01-01'::timestamp) as trade_date,
    s.adjusted,
    sysdate               as ingested_at
from spectrum_bronze.market_data s, s.results as result