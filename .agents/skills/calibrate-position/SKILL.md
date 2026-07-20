---
name: calibrate-position
description: Compare a formal position profile with AI screening advice, human decisions, interview outcomes, and final results to propose calibration. Use for profile quality reviews, repeated business rejection analysis, or screening misjudgment analysis.
---

# Calibrate Position

1. Run `calibrate-position --position "岗位名"` to build the evidence table from Markdown masters.
2. Read confirmed personal preferences, the formal profile, and the original evidence behind repeated agreements and disagreements. Separate profile requirements, personal decision preferences, systemic patterns, and individual cases; do not infer causality from small samples.
3. Attribute likely issues to profile, resume screening, interview standard, process, or individual variance.
4. Write suggested changes with before/after wording, supporting cases, counterexamples, risk, and confidence described qualitatively.
5. Do not modify `岗位.md`. Any formal profile change must be added to `待确认事项.md`, then executed only after explicit confirmation and logged in the profile change record.
6. If a recurring difference appears to reflect the user's judgment rather than the position itself, apply `$learn-recruiting-preferences` and propose a preference candidate instead of changing the profile.
