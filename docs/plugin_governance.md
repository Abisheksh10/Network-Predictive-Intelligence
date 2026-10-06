# Telecom NOC Plugin: Versioning & Ownership Policy

## 1. Ownership Model
- **Primary Owner:** NOC Architecture & Predictive Intelligence Lead.
- **Review Board:** Data Engineering Lead (owns Airflow/Spark invariants) and Lead ML Engineer (owns leakage and threshold rules).
- **Enforcement Principle:** Individual developers may NOT modify `.claude/` rules, commands, or hooks directly in project checkouts. All changes must be proposed upstream in `plugins/telecom-noc-standard/`.

## 2. Versioning Strategy (Semantic Versioning: MAJOR.MINOR.PATCH)
- **MAJOR (e.g. 2.0.0):** Breaking governance changes.
  - Adding a new `deny` boundary (e.g., blocking new directories or tool calls).
  - Changing the mandatory 4-section brief headers (`SEVERITY`, `EVIDENCE`, `INTERPRETATION`, `NEXT CHECKS`).
- **MINOR (e.g. 1.1.0):** Additive capabilities.
  - Introducing a new slash command (e.g., `/check-hotspots`).
  - Adding a new diagnostic skill or MCP endpoint wrapper without breaking existing schemas.
- **PATCH (e.g. 1.0.1):** Bug fixes and heuristic updates.
  - Tuning hook timeout settings.
  - Correcting documentation or description triggers on existing skills.

## 3. Distribution & CI/CD Invariants
- In a team setup, the plugin is pulled as a git submodule or installed via a repository bootstrap script (`python plugins/install_plugin.py`).
- CI validates that `.claude/` in developer repositories matches the latest approved plugin version checksum.