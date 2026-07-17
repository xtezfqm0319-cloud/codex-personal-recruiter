# Codex 个人招聘工作台

一个直接在 Codex 中使用的本地招聘工作台。Codex 负责理解与判断，项目 Skills 约束工作流，Python 负责确定性的文件和状态操作，Markdown 保存正式主档案。

## 环境

- Python 3.11+
- 无网页、后端、数据库或外部模型 API
- 支持读取 TXT、Markdown、PDF、DOCX 简历/纪要

建议创建虚拟环境后安装：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

若不安装项目，也可：

```bash
PYTHONPATH=06_系统 python -m recruiter --root . validate
```

## 第一次使用

1. 阅读并按实际公司情况填写 `00_公司认知/`。修改长期认知属于需确认动作。
2. 在 Codex 中说“根据这个 JD 和我讨论并新建岗位”。Codex 会使用 `create-position` Skill。
3. 把简历放入 `01_待处理/简历/`，说“处理新简历”。
4. 查看岗位下的 `本批次待人工确认.md`，用自然语言批量给出结论。
5. 把面试纪要放入 `01_待处理/面试纪要/`，说“分析新面试纪要”。
6. 终面前说“给某某生成终面简报”；结束后说“归档某某，结果为……”。

## CLI

所有命令在项目根目录执行。安装后可用 `recruiter`，未安装时用 `PYTHONPATH=06_系统 python -m recruiter`。

```bash
python -m recruiter --root . init
python -m recruiter --root . create-position --name "C端产品经理" --jd-file jd.txt --profile-file 已确认画像.md
python -m recruiter --root . ingest-resumes
python -m recruiter --root . record-resume-analysis --position "C端产品经理" --candidate "张三" --recommendation "推" --summary "..." --evidence "..." --risk "..."
python -m recruiter --root . confirm-screening --position "C端产品经理" --candidate "张三" --decision "推进"
python -m recruiter --root . ingest-interviews
python -m recruiter --root . record-interview-analysis --position "C端产品经理" --candidate "张三" --round 1 --interviewer-evaluation "..." --ai-analysis "..." --evidence "..." --unverified "..."
python -m recruiter --root . generate-final-brief --position "C端产品经理" --candidate "张三"
python -m recruiter --root . close-candidate --position "C端产品经理" --candidate "张三" --result "流程结束-人才保留" --reusable
python -m recruiter --root . rebuild-index
python -m recruiter --root . search-history --query "产品 B端"
python -m recruiter --root . calibrate-position --position "C端产品经理"
python -m recruiter --root . validate
```

需要模型判断的内容通过 `record-*` 命令显式落盘，命令本身不调用模型。CLI 的 `--help` 提供完整参数。

## 示例自然语言指令

- “读取这份 JD，先和我讨论岗位画像，有冲突请直接指出；我确认后再建岗。”
- “处理待处理区的新简历，按岗位统一排序，生成一份批量确认汇总。”
- “前两名推进，第三名待定，其余淘汰；保留 AI 建议和我结论的差异。”
- “分析王小明的二面纪要，区分面试官原话、你的分析和我的正式结论。”
- “给王小明生成终面前简报，所有判断注明证据和未验证项。”
- “王小明流程结束，因 HC 暂停未录用，但可复用，请归档。”
- “找历史上通过业务面试但因为 HC 没入职的产品候选人。”
- “根据最近结果生成岗位校准建议，不要直接修改岗位画像。”

## 测试与演示

```bash
PYTHONPATH=06_系统 pytest -q
PYTHONPATH=06_系统 python scripts/run_demo.py
```

演示会重建 `output/demo/招聘工作台演示/`，只使用脱敏模拟材料，并生成 `output/demo/端到端测试结果.md`。

## 数据安全

真实简历、纪要和候选人目录已通过 `.gitignore` 默认排除。仍应使用磁盘加密和可靠备份，并在处理真实数据前检查 Codex/ChatGPT 数据控制设置。不要把真实数据提交到公开仓库。

## 首版限制

- 项目未提供独立的既有终面简报 Prompt；当前使用 `.agents/skills/generate-final-brief/references/终面简报规则.md`，可由真实 Prompt 替换。
- 无 OCR；扫描版 PDF 若无文本层会进入待确认。
- 姓名和岗位匹配基于明确字段、文件名和岗位名称；模糊或冲突输入进入待确认，不猜测。
- Python 不做开放式语义招聘判断；需要在 Codex 对话中按 Skill 分析，再用 `record-*` 落盘。
- 自然语言历史查询由 Codex 读取索引和主档案完成；CLI 仅提供关键词只读检索。
