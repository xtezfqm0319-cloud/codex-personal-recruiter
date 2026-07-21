---
name: confirm-screening
description: Record explicit human screening decisions while preserving separate AI recommendations, then advance, hold, or archive candidates. Use after the user confirms a resume batch or gives candidate-by-candidate screening decisions.
---

# Confirm Screening

1. Read the position batch summary and candidate overviews. Map only explicit user decisions to `推进`, `待定`, or `淘汰`; ask if a reference such as “the third one” is ambiguous.
2. Run `confirm-screening` once per candidate. First-time decisions are authorized by the user's instruction; changing an existing human decision must enter `待确认事项.md`.
3. Keep advanced and held candidates active. The CLI archives initial-screen rejects and leaves a short position index.
4. Preserve `ai_recommendation` even when it differs from `human_decision`.
5. If the user explains why they disagree with a recommendation or states a reusable principle, apply `/learn-recruiting-preferences`. Do not infer a permanent preference from the decision alone.
6. Run `rebuild-index` and `validate`, then report who advances, who is held or archived, and any decision that still needs clarification. Do not narrate routine command execution.
