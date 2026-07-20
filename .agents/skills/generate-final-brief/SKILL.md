---
name: generate-final-brief
description: Generate an evidence-traceable pre-final-interview brief from a position, resume, screening analysis, all interview materials, HR notes, and candidate status. Use when preparing a candidate for final interview or decision discussion.
---

# Generate Final Brief

1. Read [终面简报规则.md](references/终面简报规则.md) completely.
2. Load confirmed personal recruiting preferences, the formal position, candidate overview, original resume/extraction, resume analysis, every interview preparation file, raw note and report, plus HR additions.
3. Resolve identity and source conflicts before writing. Do not silently choose between contradictory materials.
4. Run `generate-final-brief` to create the traceable evidence bundle, then refine its narrative in place following the reference rules without changing source hashes or human conclusions.
5. Every key conclusion must cite a local input path or nearby evidence. Label facts, judgments, preference influence, and unverified items.
6. Give one clear tendency: `建议进入录用讨论`, `谨慎推进`, `继续验证`, or `不建议推进`. Explain the three decisive reasons, the largest downside, and the single new fact that could change the tendency. Never write the formal hiring decision.
7. In conversation, lead with the tendency and decision-changing unknown; do not summarize the whole resume again.
8. Run `validate`.
