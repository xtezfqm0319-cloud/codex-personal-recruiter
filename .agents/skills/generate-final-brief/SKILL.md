---
name: generate-final-brief
description: Generate an evidence-traceable pre-final-interview brief from a position, resume, screening analysis, all interview materials, HR notes, and candidate status. Use when preparing a candidate for final interview or decision discussion.
---

# Generate Final Brief

1. Read [终面简报规则.md](references/终面简报规则.md) completely.
2. Load the formal position, candidate overview, original resume/extraction, resume analysis, every raw interview note and report, plus HR additions.
3. Resolve identity and source conflicts before writing. Do not silently choose between contradictory materials.
4. Run `generate-final-brief` to create the traceable evidence bundle, then refine its narrative in place following the reference rules without changing source hashes or human conclusions.
5. Every key conclusion must cite a local input path or nearby evidence. Label facts, judgments, and unverified items.
6. Give at most a tendency for final verification; never make the formal hiring decision.
7. Run `validate`.
