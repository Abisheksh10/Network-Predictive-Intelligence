# Lab CL2 Retrospective: Chat vs. API Execution

## 1. Interactive Chat (Claude.ai) Utility
- **Drafting & Refining Prompts:** Fast feedback loop for phrasing domain context, defining prompt template placeholders, and red-teaming checklist gaps.
- **Formulating Invariants:** Brainstorming vocabulary alternatives (e.g., approved terms to replace "congestion").

## 2. Programmatic API Integration Utility
- **Durable Memory Prepending:** Deterministically enforcing `project_context.py` across every call without relying on manual user copy-pasting.
- **Automated Security Gating:** Intercepting credentials (`check_for_secret_leakage`) before bytes ever leave the local network.
- **Contract Integrity:** Enforcing token ceilings (`GLOBAL_MAX_TOKENS = 800`) and structured schema population via `load_template()`.