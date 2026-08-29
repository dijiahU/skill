# ClickHouse Schema Reference

## Table: `opendeviationbar_cache.open_deviation_bars`

**Host**: bigblack (SSH direct, not tunnel)
**Rows**: ~139M (as of 2026-04-01)
**Symbols**: 16 | **Thresholds**: {100, 250, 500, 750} dbps

### Key Columns for Forensics

| Column                   | Type                   | Purpose                                        |
| ------------------------ | ---------------------- | ---------------------------------------------- |
| `symbol`                 | LowCardinality(String) | Trading pair (e.g., BTCUSDT)                   |
| `threshold_decimal_bps`  | UInt32                 | Threshold in decimal basis points              |
| `close_time_us`          | Int64                  | Bar close timestamp (microseconds since epoch) |
| `open_time_us`           | Int64                  | Bar open timestamp (microseconds since epoch)  |
| `open`                   | Float64                | Open price                                     |
| `high`                   | Float64                | High price                                     |
| `low`                    | Float64                | Low price                                      |
| `close`                  | Float64                | Close price                                    |
| `volume`                 | Float64                | Total volume                                   |
| `buy_volume`             | Float64                | Taker buy volume                               |
| `sell_volume`            | Float64                | Taker sell volume                              |
| `individual_trade_count` | UInt32                 | Number of individual fills                     |
| `agg_record_count`       | UInt32                 | Number of aggregated trade records             |
| `duration_us`            | Int64                  | Bar duration in microseconds                   |
| `first_agg_trade_id`     | Int64                  | First agg trade ID in bar                      |
| `last_agg_trade_id`      | Int64                  | Last agg trade ID in bar                       |
| `is_orphan`              | UInt8                  | Writer-boundary orphan flag                    |
| `is_liquidation_cascade` | UInt8                  | Liquidation cascade flag                       |
| `ofi`                    | Float64                | Order flow imbalance [-1, 1]                   |
| `trade_intensity`        | Float64                | Trade intensity metric                         |

### Derived Forensic Columns

These are computed in the query, not stored:

```sql
round((high - low) / open * 10000, 1) AS range_dbps       -- full bar range
round(abs(close - open) / open * 10000, 1) AS abs_dev_dbps -- threshold deviation
round(duration_us / 1e6, 1) AS dur_s                       -- duration in seconds
last_agg_trade_id - first_agg_trade_id + 1 AS id_span      -- agg_trade_id span
```

### Timestamp Conversion

- ClickHouse stores: microseconds since epoch (`close_time_us`, `open_time_us`)
- To human-readable: `toDateTime64(close_time_us / 1000000, 3)` in SQL
- Parquet tick `timestamp` field: also microseconds since epoch (same scale)

### Session Flag Columns

| Column                     | Type  | Purpose                 |
| -------------------------- | ----- | ----------------------- |
| `exchange_session_sydney`  | UInt8 | Sydney session active   |
| `exchange_session_tokyo`   | UInt8 | Tokyo session active    |
| `exchange_session_london`  | UInt8 | London session active   |
| `exchange_session_newyork` | UInt8 | New York session active |

### Parquet Tick Cache Schema

**Location**: `/home/tca/.cache/opendeviationbar/ticks/{SYMBOL}/{YYYY-MM-DD}.parquet`

| Column           | Type | Purpose                                    |
| ---------------- | ---- | ------------------------------------------ |
| `agg_trade_id`   | i64  | Binance aggregated trade ID (monotonic)    |
| `price`          | f64  | Execution price                            |
| `quantity`       | f64  | Trade size in base asset                   |
| `first_trade_id` | i64  | First individual fill ID in this agg trade |
| `last_trade_id`  | i64  | Last individual fill ID in this agg trade  |
| `timestamp`      | i64  | Microseconds since epoch                   |
| `is_buyer_maker` | bool | `true` = taker sell, `false` = taker buy   |
