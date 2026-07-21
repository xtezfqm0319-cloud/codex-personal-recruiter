@AGENTS.md

# Claude Code 兼容规则

- Claude Code 项目 Skills 位于 `.claude/skills/`，可由模型自动匹配，也可使用 `/skill-name` 显式调用。
- `.agents/skills/` 是 Skill 的唯一维护源；`.claude/skills/` 是通过 `scripts/sync_agent_skills.py` 生成的兼容副本，不要直接编辑。
- 修改任何正式 Skill 后，运行 `python scripts/sync_agent_skills.py --root .`，再运行 `python scripts/sync_agent_skills.py --root . --check`。
- Python CLI、Markdown 主档案、权限边界、证据要求和人工结论规则与 Codex 完全相同。
- 遇到历史文件中的“Codex 分析”字样时，将其理解为当前 AI 助手的独立分析层，不得覆盖人工正式结论。
