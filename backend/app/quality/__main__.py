"""Problem quality validation from the command line (PRD 7.7).

    python -m app.quality validate <slug> [--language L] [--max-mutants N] [--operators a,b]
                                          [--json] [--dry-run] [--from-catalog]

``--from-catalog`` loads the definition from ``app.catalog.CATALOG`` or the incident catalog, so a
problem can be validated in the sandbox without PostgreSQL. ``--dry-run`` never writes to the
database. Otherwise a MutationRun is recorded and executed synchronously. The exit status is 0 when
the quality gate approves the problem, 1 when it requires revision, and 2 on a usage or
infrastructure error.
"""
import argparse
import json
import sys

from app.quality import pipeline
from app.quality.mutation import OPERATORS


def catalog_definition(slug: str) -> dict | None:
    from app.catalog import CATALOG
    for item in CATALOG:
        if item["slug"] == slug:
            return pipeline.definition_from_catalog(item)
    try:
        from app.incidents.catalog import INCIDENTS
    except Exception:
        INCIDENTS = []
    for incident in INCIDENTS:
        problem = incident.get("problem") or {}
        if slug in (incident.get("slug"), f"incident-{incident.get('slug')}", problem.get("slug")):
            item = {**problem, "slug": problem.get("slug") or f"incident-{incident['slug']}",
                    "title": problem.get("title") or incident.get("title", slug),
                    "summary": problem.get("summary") or incident.get("summary", ""),
                    "description": problem.get("description") or problem.get("summary") or incident.get("summary", ""),
                    "taxonomy": problem.get("taxonomy")}
            return pipeline.definition_from_catalog(item)
    return None


def summarize(report: dict) -> str:
    mutation, gate = report["mutation"], report["gate"]
    lines = [f"{report['problem']['slug']} [{report['language']}]",
             *[f"  {step['step']:<24} {step['status']:<9} {step['detail']}" for step in report["pipeline"]],
             f"  mutants: {mutation['total']} total, {mutation['killed']} killed, {mutation['timed_out']} timed out, "
             f"{mutation['survived']} survived, {mutation['invalid']} invalid, {mutation['equivalent']} equivalent, "
             f"{mutation['errors']} errors",
             f"  mutation score: {mutation['score']}%  critical killed: "
             f"{mutation['critical_killed']}/{mutation['critical_scored']}",
             f"  gate: {gate['status']}"]
    lines += [f"    - {reason}" for reason in gate["reasons"]]
    return "\n".join(lines)


def validate(args) -> int:
    operators = [item.strip() for item in args.operators.split(",") if item.strip()] if args.operators else None
    if operators and set(operators) - set(OPERATORS):
        print(f"Unknown operators: {', '.join(sorted(set(operators) - set(OPERATORS)))}", file=sys.stderr)
        return 2
    if args.from_catalog or args.dry_run:
        definition = catalog_definition(args.slug) if args.from_catalog else None
        if definition is None and not args.from_catalog:
            from sqlalchemy import select

            from app.db import open_session
            from app.models import Problem
            with open_session() as db:
                problem = db.scalar(select(Problem).where(Problem.slug == args.slug))
                definition = pipeline.definition_from_problem(problem) if problem else None
                thresholds = None
                if problem is not None:
                    from app.quality.gates import effective_thresholds
                    thresholds = effective_thresholds(db, problem.category)
        else:
            thresholds = None
        if definition is None:
            print(f"Problem not found: {args.slug}", file=sys.stderr)
            return 2
        language = args.language or next(iter(definition["starters"]))
        if language not in definition["starters"]:
            print(f"{language} is not available for {args.slug}", file=sys.stderr)
            return 2
        report = pipeline.run_in_memory(definition, language, max_mutants=args.max_mutants, operators=operators,
                                        thresholds=thresholds)
    else:
        from sqlalchemy import select

        from app.db import open_session
        from app.models import MutationRun, Problem
        from app.quality.tasks import quality_run
        with open_session() as db:
            problem = db.scalar(select(Problem).where(Problem.slug == args.slug))
            if problem is None:
                print(f"Problem not found: {args.slug}", file=sys.stderr)
                return 2
            try:
                run = pipeline.create_run(db, problem, language=args.language, max_mutants=args.max_mutants,
                                          operators=operators)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            db.commit()
            run_id = run.id
        quality_run(run_id, inline=True)
        with open_session() as db:
            run = db.get(MutationRun, run_id)
            if run.status != "completed":
                print(f"Quality run {run_id} ended with status {run.status}: {run.error}", file=sys.stderr)
                return 2
            report = run.report
    print(json.dumps(report, indent=2, default=str) if args.json else summarize(report))
    return 0 if report["gate"]["status"] == "approved" else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.quality")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("validate", help="Run the problem quality pipeline")
    command.add_argument("slug")
    command.add_argument("--language")
    command.add_argument("--max-mutants", type=int, default=24)
    command.add_argument("--operators", help="Comma-separated subset of: " + ", ".join(OPERATORS))
    command.add_argument("--json", action="store_true")
    command.add_argument("--dry-run", action="store_true", help="Do not write to the database")
    command.add_argument("--from-catalog", action="store_true", help="Load the definition without a database")
    args = parser.parse_args(argv)
    if not 1 <= args.max_mutants <= 200:
        parser.error("--max-mutants must be between 1 and 200")
    return validate(args)


if __name__ == "__main__":
    sys.exit(main())
