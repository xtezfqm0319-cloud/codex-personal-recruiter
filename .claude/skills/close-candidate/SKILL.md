---
name: close-candidate
description: Close and archive an active candidate, record the final result, determine reuse eligibility, leave a short position index, and rebuild global history indexes. Use for rejection, withdrawal, offer refusal, hiring, or any completed process.
---

# Close Candidate

1. Read the full candidate record and the user's explicit final result. If the result is missing or ambiguous, ask before closing.
2. Determine `reusable` from evidence: generally true for a candidate with validated strengths whose non-hire reason is timing, HC, compensation, location, or role fit rather than integrity or a decisive capability failure. State the reason.
3. Run `close-candidate --result "..."` and include `--reusable` only when supported.
4. The CLI moves the complete folder to `03_简历库/`, retains a short position index, and never deletes originals.
5. Run `rebuild-index`, `search-history` for a sanity check, and `validate`.
6. If the user gives a reusable reason for the outcome or corrects an earlier assessment, apply `/learn-recruiting-preferences`. Otherwise do not infer a preference from the final result alone.
7. Report the final result, reuse value, and the most important lesson for future similar candidates in concise business language.
