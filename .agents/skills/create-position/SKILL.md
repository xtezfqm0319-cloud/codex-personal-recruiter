---
name: create-position
description: Discuss, challenge, confirm, and create a local recruiting position from a JD or natural-language description. Use for new positions, position-profile discussions, JD clarification, or creating a pending-calibration position and scanning reusable historical candidates.
---

# Create Position

1. Read `AGENTS.md`, `00_公司认知/`, the supplied JD or description, and existing position names.
2. Discuss before writing: summarize confirmed facts, assumptions, contradictions, missing hard constraints, success signals, screening focus, interview focus, and relaxable conditions. Ask only questions that materially affect the profile; challenge requirements that conflict or cannot be evidenced.
3. Do not create a formal position until the user explicitly confirms. If the user proceeds with open questions, set status to `待校准` and preserve them under `待校准事项`.
4. After confirmation, save the confirmed profile section to a temporary Markdown file and run `python -m recruiter --root . create-position --name "岗位名" --jd-file "路径" --profile-file "已确认画像.md"`.
5. Fill `岗位.md` from confirmed material. Separate confirmed facts, working assumptions, and unverified items. Inherit, do not silently alter, `00_公司认知/通用招聘标准.md`.
6. Run `python -m recruiter --root . search-history --query "岗位关键词" --position "岗位名"` once. Record suggestions only; never move historical candidates.
7. Run `python -m recruiter --root . rebuild-index` and `python -m recruiter --root . validate`.
