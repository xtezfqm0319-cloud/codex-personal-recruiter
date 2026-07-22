from __future__ import annotations

import argparse
import json
from pathlib import Path

from .files import extract_text
from .indexes import rebuild_indexes
from .validators import validate_workspace
from .workflows import (
    calibrate_position,
    close_candidate,
    confirm_screening,
    create_position,
    generate_final_brief,
    ingest_interviews,
    ingest_resumes,
    init_workspace,
    record_interview_analysis,
    record_resume_analysis,
    search_history,
    set_interview_decision,
)


def _root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recruiter", description="Markdown-first local recruiting workbench")
    parser.add_argument("--root", default=".", type=_root, help="workspace root (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="create runtime directories")

    command = sub.add_parser("create-position", help="create a confirmed pending-calibration position")
    command.add_argument("--name", required=True)
    source = command.add_mutually_exclusive_group(required=True)
    source.add_argument("--jd-file", type=Path)
    source.add_argument("--jd-text")
    command.add_argument("--profile-file", type=Path, help="confirmed Markdown content for the 岗位画像 section")

    sub.add_parser("ingest-resumes", help="scan and organize resume inbox")
    analysis = sub.add_parser("record-resume-analysis", help="record AI resume judgment")
    analysis.add_argument("--position", required=True)
    analysis.add_argument("--candidate", required=True)
    analysis.add_argument("--recommendation", required=True)
    analysis.add_argument("--summary", required=True)
    analysis.add_argument("--evidence", required=True)
    analysis.add_argument("--risk", required=True)
    analysis.add_argument("--unverified", default="无；仍需在面试中核验关键经历。")
    analysis.add_argument(
        "--hard-constraint-status",
        default="不适用",
        choices=["符合", "存在经确认例外", "不符合", "未验证", "不适用"],
    )
    analysis.add_argument("--exception-reason", default="")
    analysis.add_argument("--verification", default="", help="candidate-specific next verification questions")
    analysis.add_argument("--preference-impact", default="", help="confirmed personal preference applied to this judgment")

    confirm = sub.add_parser("confirm-screening", help="record initial human screening decision")
    confirm.add_argument("--position", required=True)
    confirm.add_argument("--candidate", required=True)
    confirm.add_argument("--decision", required=True, choices=["推进", "待定", "淘汰"])
    confirm.add_argument("--reason", default="", help="explicit human rationale; never inferred from AI analysis")
    confirm.add_argument(
        "--confirmed-change",
        action="store_true",
        help="execute a previously queued and explicitly reconfirmed human-decision change",
    )

    sub.add_parser("ingest-interviews", help="scan and organize interview-note inbox")
    interview = sub.add_parser("record-interview-analysis", help="record separated interview analysis")
    interview.add_argument("--position", required=True)
    interview.add_argument("--candidate", required=True)
    interview.add_argument("--round", type=int, required=True, choices=range(1, 6))
    interview.add_argument("--interviewer-evaluation", required=True)
    interview.add_argument("--ai-analysis", required=True)
    interview.add_argument("--evidence", required=True)
    interview.add_argument("--unverified", required=True)
    interview.add_argument("--question-coverage", default="")
    interview.add_argument("--strengthened", default="")
    interview.add_argument("--weakened", default="")
    interview.add_argument("--unchanged", default="")
    interview.add_argument("--contradictions", default="")
    interview.add_argument(
        "--inclination",
        default="继续验证",
        choices=["建议推进", "继续验证", "建议暂缓", "不建议推进"],
    )
    interview.add_argument("--decision-changer", default="")
    interview.add_argument("--next-verification", default="")
    interview.add_argument("--next-round-value", default="")
    interview.add_argument("--preference-impact", default="")

    decision = sub.add_parser("confirm-interview", help="record a human interview decision")
    decision.add_argument("--position", required=True)
    decision.add_argument("--candidate", required=True)
    decision.add_argument("--round", type=int, required=True, choices=range(1, 6))
    decision.add_argument("--decision", required=True)
    decision.add_argument("--reason", default="", help="explicit human reason for the formal round decision")
    decision.add_argument(
        "--confirmed-change",
        action="store_true",
        help="execute a previously queued and explicitly reconfirmed interview-decision change",
    )

    brief = sub.add_parser("generate-final-brief", help="compose an evidence-traceable final brief")
    brief.add_argument("--position", required=True)
    brief.add_argument("--candidate", required=True)
    brief.add_argument("--hr-notes", default="")

    close = sub.add_parser("close-candidate", help="finish and archive a candidate")
    close.add_argument("--position", required=True)
    close.add_argument("--candidate", required=True)
    close.add_argument("--result", required=True)
    close.add_argument("--reusable", action="store_true")

    search = sub.add_parser("search-history", help="read-only keyword search of archived candidates")
    search.add_argument("--query", required=True)
    search.add_argument("--position", default="")

    calibration = sub.add_parser("calibrate-position", help="generate calibration evidence table without changing profile")
    calibration.add_argument("--position", required=True)

    sub.add_parser("rebuild-index", help="rebuild every CSV and position table from Markdown masters")
    sub.add_parser("validate", help="validate workspace structure, evidence and policy rules")
    return parser


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root
    try:
        if args.command == "init":
            init_workspace(root)
            _print({"status": "ok", "root": root})
        elif args.command == "create-position":
            jd_text = args.jd_text
            source = None
            if args.jd_file:
                path = args.jd_file if args.jd_file.is_absolute() else root / args.jd_file
                jd_text = extract_text(path)
                source = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
            profile_text = None
            if args.profile_file:
                profile_path = args.profile_file if args.profile_file.is_absolute() else root / args.profile_file
                profile_text = profile_path.read_text(encoding="utf-8")
            target = create_position(root, args.name, jd_text, source, profile_text)
            rebuild_indexes(root)
            _print({"status": "ok", "path": target.relative_to(root)})
        elif args.command == "ingest-resumes":
            result = ingest_resumes(root)
            rebuild_indexes(root)
            _print(result)
        elif args.command == "record-resume-analysis":
            path = record_resume_analysis(
                root,
                args.position,
                args.candidate,
                args.recommendation,
                args.summary,
                args.evidence,
                args.risk,
                args.unverified,
                args.hard_constraint_status,
                args.exception_reason,
                args.verification,
                args.preference_impact,
            )
            rebuild_indexes(root)
            _print({"status": "ok", "path": path.relative_to(root)})
        elif args.command == "confirm-screening":
            path = confirm_screening(
                root,
                args.position,
                args.candidate,
                args.decision,
                args.reason,
                args.confirmed_change,
            )
            rebuild_indexes(root)
            _print({"status": "ok", "path": path.relative_to(root)})
        elif args.command == "ingest-interviews":
            result = ingest_interviews(root)
            rebuild_indexes(root)
            _print(result)
        elif args.command == "record-interview-analysis":
            path = record_interview_analysis(
                root,
                args.position,
                args.candidate,
                args.round,
                args.interviewer_evaluation,
                args.ai_analysis,
                args.evidence,
                args.unverified,
                args.question_coverage,
                args.strengthened,
                args.weakened,
                args.unchanged,
                args.contradictions,
                args.inclination,
                args.decision_changer,
                args.next_verification,
                args.next_round_value,
                args.preference_impact,
            )
            rebuild_indexes(root)
            _print({"status": "ok", "path": path.relative_to(root)})
        elif args.command == "confirm-interview":
            path = set_interview_decision(
                root,
                args.position,
                args.candidate,
                args.round,
                args.decision,
                args.reason,
                args.confirmed_change,
            )
            rebuild_indexes(root)
            _print({"status": "ok", "path": path.relative_to(root)})
        elif args.command == "generate-final-brief":
            path = generate_final_brief(root, args.position, args.candidate, args.hr_notes)
            rebuild_indexes(root)
            _print({"status": "ok", "path": path.relative_to(root)})
        elif args.command == "close-candidate":
            path = close_candidate(root, args.position, args.candidate, args.result, args.reusable)
            rebuild_indexes(root)
            _print({"status": "ok", "path": path.relative_to(root)})
        elif args.command == "search-history":
            _print(search_history(root, args.query, args.position))
        elif args.command == "calibrate-position":
            path = calibrate_position(root, args.position)
            _print({"status": "ok", "path": path.relative_to(root)})
        elif args.command == "rebuild-index":
            _print(rebuild_indexes(root))
        elif args.command == "validate":
            issues = validate_workspace(root)
            _print([issue.__dict__ for issue in issues])
            return 1 if any(issue.level == "ERROR" for issue in issues) else 0
        return 0
    except Exception as exc:
        _print({"status": "error", "type": type(exc).__name__, "message": str(exc)})
        return 1
