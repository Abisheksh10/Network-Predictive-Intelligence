# CLAUDE.md

Operational guardrails for this repository (Milan telecom NOC intelligence platform:
landing CSV → Spark → MySQL star schema → FastAPI → React dashboard / Claude assistant).

These 6 rules are **non-negotiable**. They apply to every phase (Airflow DAGs, phase3
warehouse loader, phase4 API, phase6 ML/anomaly, phase7 assistant, phase5 dashboard) and
to any code, query, or answer you generate. If a request conflicts with one of these
rules, say so explicitly instead of silently complying.

## 1. Canonical grain: one grid per hourly timestamp

- The atomic unit of `fact_network_activity` is exactly one row per `(time_key, grid_id)`,
  where `time_key` represents a single hourly bucket (`yyyyMMddHH`), matching `dim_time`.
- Never write, propose, or accept a query/transform that fans this out (e.g. joining in a
  way that produces duplicate `(time_key, grid_id)` pairs, sub-hourly buckets, or
  multi-grid rows collapsed into one).
- Any load into the warehouse must be verifiable as row-count-identical to its Spark
  source (`spark_fact_count == mysql_fact_count`) — treat a mismatch as a hard failure,
  not a warning.
- When adding a new table or feature, key it the same way unless there is an explicit,
  stated reason to change grain — and if you do change grain, call it out.

## 2. Proportional activity measures — never counts or MB

- All activity fields (`sms_in`, `sms_out`, `call_in`, `call_out`, `internet_activity`,
  `total_sms`, `total_calls`, `total_activity`, `internet_share`, anomaly/risk scores)
  are proportional interaction units derived from the CDR dataset's normalized activity
  signal — **not** raw call counts, SMS counts, bytes, or MB/GB.
- Never label, document, or narrate these values as "calls", "messages", or a data
  volume (MB/GB). Do not introduce new fields that reintroduce raw counts/bytes as a
  primary measure without flagging the deviation.
- When describing activity to a user, use the existing unit vocabulary (activity units,
  share, score) — do not invent throughput or bandwidth framing.

## 3. Never assert confirmed congestion

- The pipeline monitors **activity volume**, not network/line capacity. Never use the
  word "congestion" (or equivalent capacity-exhaustion claims) as an assertion of fact,
  in code comments, API responses, alert text, or assistant output.
- Anomaly/alert language must stay in the observed vocabulary already used in this repo:
  direction (`HIGH` / `LOW` / `NORMAL`), `is_anomaly`, `anomaly_score`, `risk_level`
  (`LOW` / `CRITICAL`). These are statistical deviations from a historical baseline, not
  capacity verdicts.
- If a hypothesis about congestion-like causes is genuinely useful, it must be labeled as
  inference/hypothesis (see Rule 6's evidence/inference separation), never stated as
  observed fact.

## 4. Join geography on `properties.cellId`

- The only valid spatial join key between `milano-grid.geojson` and any table/response is
  `feature["properties"]["cellId"]` ↔ `grid_id`.
- `dim_grid` stores only derived centroid coordinates (`centroid_lon`, `centroid_lat`) and
  a `geometry_ref` pointer back to the GeoJSON — never raw polygon/geometry columns in
  fact or dimension tables outside `dim_grid` itself.
- Any new spatial feature (neighbours, maps, clustering) must resolve geography through
  `grid_id` → `cellId`, not by re-deriving coordinates from a different source or by
  matching on centroid proximity as a substitute for the authoritative ID join.

## 5. AS_OF convention defines "now"

- This dataset is historical (Milan CDR, November 2013). "Now" for every query, API
  response, alert, and assistant answer is **`AS_OF`** — defined as the effective cutoff
  timestamp, defaulting to `MAX(dim_time.timestamp)` in the warehouse — never the actual
  wall-clock date.
- Never default to, infer, or suggest a current real-world date (e.g. 2024+) for
  filtering, "latest" data, or freshness reasoning. If a caller doesn't supply `as_of`,
  resolve it dynamically from the warehouse; do not hardcode a date.
- Any freshness/staleness assessment (`freshness_indicator`, `freshness_hours`) is
  computed relative to `AS_OF`, not to the system clock.

## 6. Pipeline status record gates data trustworthiness

- Before asserting anything about current network state as fact, check
  `GET /pipeline/status` (backed by the DE7/DE8 validation chain: ingest check → raw
  validation → processed validation → warehouse validation → quality check).
- The top-level `healthy` boolean is the single gate. If `healthy` is `false` or the
  pipeline status cannot be retrieved, you must say so explicitly and avoid presenting
  downstream metrics (activity, hotspots, anomalies, risk) as trustworthy fact.
- Always surface the `AS_OF` timestamp and pipeline health alongside any substantive
  claim — do not answer NOC questions from tool/API data without first establishing
  pipeline trust and freshness context.

---

### Supporting practices (not new rules, just how the above are enforced today)

- `phase3/de6.py` — `validate_acceptance_criteria()` is the executable check for Rules 1
  and 4 (row-count parity, no geometry in fact table, unique `dim_grid`).
- `AirFlow/dags/Phase3/DE7`, `DE8` — `run_pipeline()` is the executable check behind
  Rule 6's `healthy` flag.
- `phase6/anomaly.py` — the reference implementation for Rule 3's vocabulary
  (`direction`, `anomaly_score`, `reason`), and for baseline-relative rather than
  wall-clock-relative comparisons (Rule 5).
- `phase7/claude_insight.py`'s `SYSTEM_PROMPT` is the canonical statement of Rules 3, 5,
  and 6 for the assistant specifically — keep it in sync with this file if either changes.
