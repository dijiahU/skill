# Evolution Log

## 2026-04-02 — Initial creation

**Trigger**: Flowsurface BPR10 chart showed oversized bars around 2026-02-07 06:43 UTC. Investigation traced root cause to 7 liquidation cascades totaling ~420 BTC / $29M in 66 seconds, each processed as single matching engine batches (802 trades at same microsecond timestamp).

**Evidence**: ClickHouse showed bars with 0s duration and 22-28 dbps deviation on 100 dbps threshold. Parquet analysis confirmed 95%+ taker-sell dominance, $70-$153 individual trade-to-trade price gaps exceeding the $70 threshold, and single-timestamp bursts of 500-850 trades.

**Methodology encoded**: 3-layer drill-down (ClickHouse overview → anomaly isolation → Parquet trade-level root cause) with classification table for distinguishing algorithm bugs from market microstructure.
