---
description: Check data pipeline health and data trustworthiness
---
Call GET http://127.0.0.1:8000/pipeline/status.
Summarize whether the analytics layer is healthy and trustworthy as of the AS_OF timestamp.
Explicitly name any rejected rows, handled nulls, or freshness lag.