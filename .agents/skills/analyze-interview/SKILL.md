---
name: analyze-interview
description: Match and analyze local interview notes for active candidates across one to five rounds. Use for new interview transcripts, a named candidate's interview, or updating interview evidence and workflow status.
---

# Analyze Interview

1. Read `AGENTS.md`, the position, candidate overview, resume analysis, and files in `01_待处理/面试纪要/`.
2. Run `ingest-interviews`. Do not guess an ambiguous candidate, position, or round; leave it in the pending area.
3. Read the preserved raw note and extraction. Separate: interviewer's evaluation (faithful attribution), Codex independent analysis, evidence, and unverified items.
4. Record the analysis with `record-interview-analysis --round 1..5`. Do not write a human conclusion.
5. If the user explicitly gives the formal round decision, run `confirm-interview`. Never overwrite a different existing human decision without a pending confirmation.
6. Run `rebuild-index` and `validate`.
