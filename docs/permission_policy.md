# Claude Code Permissions & Security Policy

## 1. Classification Matrix
- **DENY (Blocked Outright):**
  - `data/` modifications and deletions: Prevents accidental destruction or corruption of raw telemetry records (`data/raw/` is an immutable landing zone).
  - `.env` and secrets: Prevents credentials, database passwords, and API keys from leaking into the model context or logs.
  - Destructive filesystem commands (`rm -rf`, `del /s /q`): Hard safety boundary against recursive deletions.

- **ASK (Confirmation Required):**
  - Edits to `Airflow/dags/` and pipeline `config.yaml`: Airflow scheduling and pipeline DAG changes impact the production batch run.
  - Package installations (`pip install`, `npm install`): Prevents unvetted dependencies or supply-chain drift.
  - Database schema changes (`mysql`): Prevents unreviewed DDL executions or table alterations on the warehouse.

- **ALLOW (Auto-Approved):**
  - Test executions (`pytest`, `python -m pytest`): Read-only verification that speeds up the feedback loop.
  - Linter & formatting checks (`ruff`, `black`, `git status`, `git diff`): Non-destructive read-only code quality inspection.
  - Safe source file reads: Inspecting `phase*`, `Airflow/dags`, and `docs` without mutation.

## 2. Managed Settings for Team Environments
In enterprise and multi-developer teams, permissions in `.claude/settings.json` are committed to git to enforce the shared floor. High-security denials (such as blocking `.env` reads and `rm -rf`) can also be deployed via system-level enterprise managed settings (`~/.claude/settings.json`) where individual developers cannot override them.