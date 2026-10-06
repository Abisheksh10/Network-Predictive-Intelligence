# C9: Multi-Agent Orchestration Analysis & Evaluation

## 1. When Subagents Add Real Value
- **Heterogeneous Tool Domains:** Subagents excel when specialists require fundamentally different data silos (e.g., Kafka/Airflow operational logs vs. MySQL star schema analytics vs. Kubernetes ingress metrics) where combining all schemas into one single agent context would exceed context boundaries or cause tool confusion.
- **Independent Failure Boundaries:** If the ML model service goes down, the Data Pipeline and Network Trend agents can still complete their assessments without causing the entire investigation to abort.

## 2. When a Single Agent Would Have Been Better (Acceptance Criterion 3 Case)
- **Standard Single-Grid Diagnostics (e.g., Grid 4821):** For standard, routine operational queries, **a single agent with access to all 7 tools is significantly better**.
- **Reasoning:**
  1. **Token & Latency Overhead:** Running 4 subagents plus 1 supervisor required 5 distinct LLM inferences (~3,500 tokens). A single agent completed the exact same diagnosis in Lab C2 with just 2 tool-calling turns (~1,200 tokens).
  2. **Synthetic Conflicts:** Subagents isolated from each other lack holistic context (e.g., the ML agent doesn't see if the pipeline is stale, and the Pipeline agent doesn't know if a surge occurred). The supervisor must spend extra reasoning tokens reconciling facts that a single agent sees naturally.