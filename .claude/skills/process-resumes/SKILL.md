---
name: process-resumes
description: Process new local resumes into position candidate records with traceable four-tier recommendations. Use when asked to scan, organize, screen, summarize, rank, or prepare a batch confirmation for resumes in the inbox.
---

# Process Resumes

1. Read `AGENTS.md`, company standards, `00_公司认知/个人招聘判断偏好.md`, each target `岗位.md`, and all files in `01_待处理/简历/`.
2. Run `python -m recruiter --root . ingest-resumes`. Do not guess ambiguous names or positions; inspect `待确认事项.md`.
3. For every successfully ingested resume, read the original extraction, its SHA-256 trace, and the position profile. Analyze role-relevant evidence, ownership, result strength, risks, unverified items, education policy, and applicable confirmed personal preferences.
4. Use only `强推`, `推`, `建议待定`, or `建议淘汰`; never assign scores. A 211 recommendation requires a concrete exception reason. Non-985/211 or unverified education defaults to `建议淘汰`.
5. Record each judgment with `record-resume-analysis`; never overwrite the original resume.
6. Run `rebuild-index`, then apply `/compare-candidates` for each affected position. Write a real relative ordering, including why adjacent candidates differ and whom to prioritize if interview capacity is limited.
7. Update `本批次待人工确认.md` with concise business summaries and proposed decisions. In conversation, lead with the top candidates, the hardest trade-off, and the smallest set of decisions needed from the user.
8. Stop before writing human decisions. Ask the user to confirm the batch; use `/confirm-screening` afterward. Do not explain routine file operations unless something failed.
