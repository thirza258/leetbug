from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import attempts, policy, taxonomy
from app.analytics import TERMINAL, leaderboard_rows, personal_stats, platform_stats
from app.auth import (
    COOKIE,
    DUMMY_HASH,
    current_user,
    hash_token,
    optional_user,
    passwords,
    public_user,
    record_activity,
    require_admin,
    start_session,
)
from app.config import settings
from app.db import get_db
from app.events import record_event
from app.limits import rate_limit
from app.models import (
    AuthSession,
    Bookmark,
    Discussion,
    Hint,
    Problem,
    ProblemSubmission,
    Reply,
    Submission,
    User,
    Vote,
    now,
)
from app.schemas import (
    AdminReviewAction,
    DiscussionCreate,
    HintCreate,
    Login,
    ProblemSubmissionCreate,
    ProfileUpdate,
    Register,
    ReplyCreate,
    SubmissionCreate,
)
from app.sitemap import generate_robots_txt, generate_sitemap_xml
from app.tasks import evaluate, hint_task

router = APIRouter(prefix="/api")


def get_problem(db, slug, user=None):
    """Look up a problem the user may see. Non-public problems are reported as missing."""
    problem = db.scalar(select(Problem).where(Problem.slug == slug))
    if not problem or not policy.can_view_problem(db, user, problem):
        raise HTTPException(404, "Case study not found.")
    return problem


def has_solved(db, user_id, problem_id):
    # Assessment work never unlocks practice solutions or library progress.
    return bool(db.scalar(select(Submission.id).where(Submission.user_id == user_id,
                                                     Submission.problem_id == problem_id,
                                                     Submission.assessment_session_id.is_(None),
                                                     Submission.kind == "submit", Submission.status == "passed").limit(1)))


def problem_summary(problem, solved=False, attempted=False, bookmarked=False, acceptance=None):
    return {"id": problem.id, "slug": problem.slug, "title": problem.title, "summary": problem.summary,
            "category": problem.category, "difficulty": problem.difficulty, "tags": problem.tags,
            "languages": list(problem.starters), "estimated_minutes": problem.estimated_minutes,
            "status": "solved" if solved else "attempted" if attempted else "todo",
            "bookmarked": bookmarked, "acceptance_rate": acceptance}


def submission_view(submission, problem):
    return {key: getattr(submission, key) for key in (
        "id", "problem_id", "language", "mode", "kind", "code", "prompt", "generated_code", "status", "results",
        "error", "runtime_ms", "memory_kb", "turnaround_ms", "llm_tokens", "prompt_words", "shared", "created_at", "completed_at",
        "attempt_id", "assessment_session_id", "diagnosis_id", "diff_stats", "quality",
    )} | {"problem_title": problem.title, "problem_slug": problem.slug}


def hint_view(hint):
    return {key: getattr(hint, key) for key in ("id", "level", "status", "text", "sources", "retrieval", "error")}


def enqueue(db, task, record):
    try:
        task.delay(record.id)
    except Exception as exc:
        record.status, record.error = "error", "The queue is temporarily unavailable. Please try again."
        db.commit()
        raise HTTPException(503, record.error) from exc


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    return {"name": "LeetBug", "version": "1.0.0", "languages": ["python", "java", "javascript", "cpp", "go"],
            "ai_enabled": settings.ai_enabled, "ai_provider": settings.ai_provider,
            "ai_model": settings.ai_model if settings.ai_enabled else None,
            "hint_failure_threshold": settings.hint_failure_threshold, "demo_available": settings.seed_demo_user,
            "problem_count": db.scalar(select(func.count()).select_from(Problem).where(Problem.visibility == "public")),
            "features": {"diagnosis": True, "incidents": True, "assessments": True, "adaptive_ai": True,
                         "mutation_testing": True, "organizations": True}}


@router.get("/taxonomy")
def taxonomy_view():
    return taxonomy.taxonomy_document()


@router.post("/auth/register", status_code=201)
def register(data: Register, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(f"auth:{request.client.host}", 15)
    user = User(email=str(data.email).lower(), username=data.username.lower(), password_hash=passwords.hash(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "That email or username is already registered.") from exc
    return start_session(db, response, user)


@router.post("/auth/login")
def login(data: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(f"auth:{request.client.host}", 15)
    rate_limit(f"login:{str(data.email).lower()}", 15)
    user = db.scalar(select(User).where(User.email == str(data.email).lower()))
    valid = passwords.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if not user or not valid:
        raise HTTPException(401, "Email or password is incorrect.")
    old = request.cookies.get(COOKIE)
    if old:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(old)))
    return start_session(db, response, user)


@router.get("/auth/me")
def me(request: Request, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    if not user:
        return {"user": None, "csrf_token": None}
    record_activity(db, user)
    return {"user": public_user(user), "csrf_token": request.state.auth_session.csrf_token}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(request.state.auth_session)
    db.commit()
    response.delete_cookie(COOKIE, path="/api", secure=settings.cookie_secure, httponly=True, samesite="lax")


@router.patch("/auth/profile")
def update_profile(data: ProfileUpdate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.bio = data.bio.strip()
    db.commit()
    return public_user(user)


@router.get("/problems")
def problems(q: str = Query("", max_length=100), category: str = "", difficulty: str = "", language: str = "",
             status: str = "", tag: str = "", bookmarked: bool = False,
             sort: Literal["recommended", "difficulty", "title"] = "recommended",
             page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
             user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    query = select(Problem).where(Problem.visibility == "public").order_by(Problem.id)
    if category:
        query = query.where(Problem.category == category)
    if difficulty:
        query = query.where(Problem.difficulty == difficulty)
    rows = list(db.scalars(query))
    own = list(db.scalars(select(Submission).where(Submission.user_id == user.id,
                                                   Submission.assessment_session_id.is_(None)))) if user else []
    solved = {r.problem_id for r in own if r.status == "passed" and r.kind == "submit"}
    attempted = {r.problem_id for r in own}
    saved = set(db.scalars(select(Bookmark.problem_id).where(Bookmark.user_id == user.id))) if user else set()
    counts = {}
    for pid, result_status, count in db.execute(select(Submission.problem_id, Submission.status, func.count())
                                              .where(Submission.kind == "submit", Submission.status.in_(TERMINAL))
                                              .group_by(Submission.problem_id, Submission.status)):
        total, passed = counts.get(pid, (0, 0))
        counts[pid] = (total + count, passed + (count if result_status == "passed" else 0))
    items = []
    for problem in rows:
        if language and language not in problem.starters:
            continue
        if tag and tag not in problem.tags:
            continue
        if q.lower() not in " ".join([problem.title, problem.summary, *problem.tags]).lower():
            continue
        total, passed = counts.get(problem.id, (0, 0))
        item = problem_summary(problem, problem.id in solved, problem.id in attempted, problem.id in saved,
                               round(passed / total * 100, 1) if total else None)
        if status and item["status"] != status or bookmarked and not item["bookmarked"]:
            continue
        items.append(item)
    if sort == "difficulty":
        items.sort(key=lambda item: ({"easy": 0, "medium": 1, "hard": 2}[item["difficulty"]], item["id"]))
    if sort == "title":
        items.sort(key=lambda item: item["title"])
    return {"items": items[(page - 1) * limit:page * limit], "total": len(items), "page": page, "limit": limit,
            "tags": sorted({tag for p in rows for tag in p.tags})}


def problem_payload(db, problem, user=None, *, include_progress=True):
    """Public problem detail. Never includes solutions, hidden tests, hints, explanations or rubrics."""
    solved = has_solved(db, user.id, problem.id) if user and include_progress else False
    failures = db.scalar(select(func.count()).select_from(Submission).where(
        Submission.user_id == user.id, Submission.problem_id == problem.id,
        Submission.status.in_(TERMINAL - {"passed"}))) if user else 0
    assistance = policy.assistance_for(db, user, problem) if user else policy.Assistance()
    return {**problem_summary(problem, solved, failures > 0,
                               bool(db.get(Bookmark, (user.id, problem.id))) if user else False),
            "description": problem.description, "requirements": problem.requirements, "starters": problem.starters,
            "public_tests": [{"name": t["name"], "input": t["input"], "expected": t["expected"], "assertions": t["assertions"]}
                             for t in problem.tests if not t["hidden"]],
            "hidden_test_count": sum(t["hidden"] for t in problem.tests), "failed_attempts": failures,
            "hints_unlocked": failures >= settings.hint_failure_threshold and policy.hint_level_cap(assistance) != 0,
            "visibility": problem.visibility, "version": problem.version, "diagnosis_mode": problem.diagnosis_mode,
            "diagnosis_required": problem.diagnosis_mode == "required" or assistance.source == "assessment" and bool(
                ((assistance.session.config_snapshot or {}).get("configuration") or {}).get("diagnosis_required")),
            "taxonomy": taxonomy.describe(taxonomy.classify_problem(problem)),
            "assistance": assistance.as_dict()}


@router.get("/problems/{slug}")
def problem_detail(slug: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    return problem_payload(db, get_problem(db, slug, user), user)


@router.post("/problems/{slug}/bookmark")
def bookmark(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    problem = get_problem(db, slug, user)
    existing = db.get(Bookmark, (user.id, problem.id))
    if existing:
        db.delete(existing)
    else:
        db.add(Bookmark(user_id=user.id, problem_id=problem.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"bookmarked": bool(db.get(Bookmark, (user.id, problem.id)))}


@router.get("/problems/{slug}/solutions")
def solutions(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    problem = get_problem(db, slug, user)
    locked = policy.solutions_locked(db, user, problem)
    if locked:
        raise HTTPException(403, locked)
    if not has_solved(db, user.id, problem.id):
        raise HTTPException(403, "Pass all public and hidden tests with Submit Fix to unlock solutions.")
    shared = db.execute(select(Submission, User.username).join(User, Submission.user_id == User.id)
                        .where(Submission.problem_id == problem.id, Submission.shared.is_(True),
                               Submission.kind == "submit", Submission.status == "passed")
                        .order_by(Submission.prompt_words, Submission.created_at).limit(30))
    return {"explanation": problem.explanation, "solutions": problem.solutions,
            "community": [{"id": row.id, "username": username, "language": row.language, "mode": row.mode,
                           "code": row.generated_code or row.code, "prompt": row.prompt,
                           "prompt_words": row.prompt_words, "runtime_ms": row.runtime_ms} for row, username in shared]}


@router.post("/submissions", status_code=202)
def submit(data: SubmissionCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(f"submit:{user.id}", 20)
    problem = db.get(Problem, data.problem_id)
    if not problem or not policy.can_view_problem(db, user, problem) or data.language not in problem.starters:
        raise HTTPException(422, "That language is not available for this case study.")
    context = attempts.resolve_context(db, user, problem, assessment_session_id=data.assessment_session_id,
                                       incident_session_id=data.incident_session_id)
    assistance = policy.assistance_for(db, user, problem, context.assessment_session)
    if context.assessment_session is not None:
        configuration = (context.assessment_session.config_snapshot or {}).get("configuration", {})
        allowed = configuration.get("languages") or []
        if allowed and data.language not in allowed:
            raise HTTPException(422, "That language is not allowed in this assessment.")
        limit = configuration.get("max_attempts")
        if data.kind == "submit" and limit and db.scalar(select(func.count()).select_from(Submission).where(
                Submission.attempt_id == context.attempt.id, Submission.kind == "submit")) >= int(limit):
            raise HTTPException(409, f"This assessment allows {limit} submissions per challenge.")
    if data.mode == "ai":
        policy.ensure_ai_allowed(assistance, generation=True)
        if not settings.ai_enabled:
            raise HTTPException(503, "AI fixes need a configured OpenRouter or Ollama model.")
        if len(data.prompt.strip()) < 10:
            raise HTTPException(422, "Describe the bug and intended fix in at least 10 characters.")
        rate_limit(f"ai:{user.id}", 10)
    diagnosis = attempts.latest_diagnosis(db, context.attempt.id)
    if data.kind == "submit" and diagnosis is None and attempts.diagnosis_required(problem, context):
        raise HTTPException(428, "Submit your diagnosis of the root cause before submitting a fix.")
    # Lock the account row so simultaneous requests cannot exceed the active job cap.
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    pending = db.scalar(select(func.count()).select_from(Submission).where(
        Submission.user_id == user.id, Submission.status.in_(["queued", "running"])))
    if pending >= 2:
        raise HTTPException(409, "Wait for your current evaluations to finish before starting another.")
    submission = Submission(user_id=user.id, **data.model_dump(exclude={"assessment_session_id", "incident_session_id"}),
                            prompt_words=len(data.prompt.split()), attempt_id=context.attempt.id,
                            assessment_session_id=context.assessment_session.id if context.assessment_session else None,
                            diagnosis_id=diagnosis.id if diagnosis else None,
                            diff_stats=attempts.diff_stats(problem.starters.get(data.language, ""), data.code))
    db.add(submission)
    db.flush()
    record_event(db, "submission.created", user_id=user.id, problem_id=problem.id, attempt_id=context.attempt.id,
                 assessment_session_id=submission.assessment_session_id,
                 incident_session_id=context.incident_session.id if context.incident_session else None,
                 kind=data.kind, mode=data.mode, language=data.language, submission_id=submission.id)
    db.commit()
    record_activity(db, user)
    enqueue(db, evaluate, submission)
    return submission_view(submission, problem)


@router.get("/submissions")
def submission_history(problem_id: int | None = None, page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100),
                       user: User = Depends(current_user), db: Session = Depends(get_db)):
    condition = [Submission.user_id == user.id]
    if problem_id:
        condition.append(Submission.problem_id == problem_id)
    total = db.scalar(select(func.count()).select_from(Submission).where(*condition))
    rows = db.execute(select(Submission, Problem).join(Problem).where(*condition).order_by(Submission.created_at.desc())
                      .offset((page - 1) * limit).limit(limit))
    return {"items": [submission_view(row, problem) for row, problem in rows], "total": total, "page": page, "limit": limit}


@router.get("/submissions/{submission_id}")
def submission_detail(submission_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    submission = db.get(Submission, submission_id)
    if not submission or submission.user_id != user.id:
        raise HTTPException(404, "Submission not found.")
    return submission_view(submission, db.get(Problem, submission.problem_id))


@router.post("/submissions/{submission_id}/share")
def share_submission(submission_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    submission = db.get(Submission, submission_id)
    if not submission or submission.user_id != user.id:
        raise HTTPException(404, "Submission not found.")
    if submission.status != "passed" or submission.kind != "submit":
        raise HTTPException(403, "Only a fully accepted fix can be shared.")
    submission.shared = not submission.shared
    db.commit()
    return {"shared": submission.shared}


@router.post("/problems/{slug}/hints", status_code=202)
@router.post("/problems/{slug}/adaptive-hint", status_code=202)
def request_hint(slug: str, data: HintCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    problem = get_problem(db, slug, user)
    if data.language not in problem.starters:
        raise HTTPException(422, "Choose a supported language.")
    context = attempts.resolve_context(db, user, problem, assessment_session_id=data.assessment_session_id,
                                       incident_session_id=data.incident_session_id)
    assistance = policy.assistance_for(db, user, problem, context.assessment_session)
    if policy.hint_level_cap(assistance) == 0:
        raise HTTPException(403, "Hints are disabled for this assessment.")
    failures = db.scalar(select(func.count()).select_from(Submission).where(
        Submission.user_id == user.id, Submission.problem_id == problem.id,
        Submission.status.in_(TERMINAL - {"passed"})))
    if failures < settings.hint_failure_threshold:
        raise HTTPException(403, f"Hints unlock after {settings.hint_failure_threshold} unsuccessful evaluations.")
    rate_limit(f"hint:{user.id}", 5)
    db.scalar(select(User).where(User.id == user.id).with_for_update())
    scope = [Hint.user_id == user.id, Hint.problem_id == problem.id, Hint.language == data.language,
             Hint.assessment_session_id == context.assessment_session.id if context.assessment_session
             else Hint.assessment_session_id.is_(None)]
    existing = db.scalar(select(Hint).where(*scope, Hint.status.in_(["queued", "running"])))
    if existing:
        return hint_view(existing)
    previous = list(db.scalars(select(Hint).where(*scope, Hint.status == "completed").order_by(Hint.level)))
    if previous and previous[-1].level >= len(problem.hints):
        return hint_view(previous[-1])
    level = len(previous) + 1
    if previous:
        try:
            policy.ensure_hint_allowed(assistance, level)
        except HTTPException:
            return hint_view(previous[-1])
    hint = Hint(user_id=user.id, problem_id=problem.id, language=data.language, level=level,
                attempt_id=context.attempt.id,
                assessment_session_id=context.assessment_session.id if context.assessment_session else None,
                context={"code": data.code} if data.code else None)
    db.add(hint)
    db.flush()
    record_event(db, "hint.requested", user_id=user.id, problem_id=problem.id, attempt_id=context.attempt.id,
                 assessment_session_id=hint.assessment_session_id, level=level)
    db.commit()
    enqueue(db, hint_task, hint)
    return hint_view(hint)


@router.get("/hints/{hint_id}")
def get_hint(hint_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    hint = db.get(Hint, hint_id)
    if not hint or hint.user_id != user.id:
        raise HTTPException(404, "Hint not found.")
    return hint_view(hint)


@router.get("/analytics/me")
def analytics_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return personal_stats(db, user)


@router.get("/analytics/platform")
def analytics_platform(db: Session = Depends(get_db)):
    return platform_stats(db)


@router.get("/leaderboard")
def leaderboard(mode: Literal["all", "ai"] = "all", problem_id: int | None = None, db: Session = Depends(get_db)):
    return {"items": leaderboard_rows(db, mode, problem_id), "mode": mode}


def discussion_view(db, discussion, user=None, detail=False):
    author = db.get(User, discussion.author_id)
    problem = db.get(Problem, discussion.problem_id) if discussion.problem_id else None
    votes = db.scalar(select(func.count()).select_from(Vote).where(Vote.discussion_id == discussion.id))
    voted = bool(user and db.scalar(select(Vote.id).where(Vote.discussion_id == discussion.id, Vote.user_id == user.id)))
    replies = db.execute(select(Reply, User.username).join(User, Reply.author_id == User.id)
                         .where(Reply.discussion_id == discussion.id).order_by(Reply.created_at)).all()
    return {"id": discussion.id, "title": discussion.title, "body": discussion.body,
            "author": author.username, "author_id": author.id, "created_at": discussion.created_at,
            "problem_id": discussion.problem_id, "problem_title": problem.title if problem else None,
            "problem_slug": problem.slug if problem else None, "votes": votes, "voted": voted, "reply_count": len(replies),
            "replies": [{"id": reply.id, "body": reply.body, "author": username, "author_id": reply.author_id,
                         "created_at": reply.created_at} for reply, username in replies] if detail else []}


@router.get("/discussions")
def discussions(q: str = Query("", max_length=100), problem_id: int | None = None, page: int = Query(1, ge=1),
                user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    query = select(Discussion)
    if q:
        query = query.where(or_(Discussion.title.icontains(q, autoescape=True), Discussion.body.icontains(q, autoescape=True)))
    if problem_id:
        query = query.where(Discussion.problem_id == problem_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Discussion.created_at.desc()).offset((page - 1) * 20).limit(20))
    return {"items": [discussion_view(db, row, user) for row in rows], "total": total, "page": page, "limit": 20}


@router.post("/discussions", status_code=201)
def create_discussion(data: DiscussionCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(f"community:{user.id}", 10)
    if data.problem_id and not db.get(Problem, data.problem_id):
        raise HTTPException(404, "Case study not found.")
    row = Discussion(author_id=user.id, **data.model_dump())
    db.add(row)
    db.commit()
    return discussion_view(db, row, user, True)


def find_discussion(db, discussion_id):
    row = db.get(Discussion, discussion_id)
    if not row:
        raise HTTPException(404, "Discussion not found.")
    return row


@router.get("/discussions/{discussion_id}")
def discussion_detail(discussion_id: str, user: User | None = Depends(optional_user), db: Session = Depends(get_db)):
    return discussion_view(db, find_discussion(db, discussion_id), user, True)


@router.post("/discussions/{discussion_id}/replies", status_code=201)
def reply(discussion_id: str, data: ReplyCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = find_discussion(db, discussion_id)
    rate_limit(f"community:{user.id}", 10)
    db.add(Reply(discussion_id=row.id, author_id=user.id, body=data.body))
    db.commit()
    return discussion_view(db, row, user, True)


@router.post("/discussions/{discussion_id}/vote")
def vote(discussion_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = find_discussion(db, discussion_id)
    existing = db.scalar(select(Vote).where(Vote.discussion_id == row.id, Vote.user_id == user.id))
    if existing:
        db.delete(existing)
    else:
        db.add(Vote(discussion_id=row.id, user_id=user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return discussion_view(db, row, user, True)


@router.delete("/discussions/{discussion_id}", status_code=204)
def delete_discussion(discussion_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = find_discussion(db, discussion_id)
    if row.author_id != user.id:
        raise HTTPException(403, "You can only delete your own discussions.")
    db.delete(row)
    db.commit()


@router.delete("/replies/{reply_id}", status_code=204)
def delete_reply(reply_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(Reply, reply_id)
    if not row:
        raise HTTPException(404, "Reply not found.")
    if row.author_id != user.id:
        raise HTTPException(403, "You can only delete your own replies.")
    db.delete(row)
    db.commit()


# ── user problem submissions ──────────────────────────────


def slugify(text: str) -> str:
    import re
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug[:100]


def submission_problem_view(sub, author_username=None):
    return {key: getattr(sub, key) for key in (
        "id", "author_id", "title", "slug", "summary", "description", "category",
        "difficulty", "tags", "language", "buggy_code", "fixed_code", "test_cases",
        "hint", "status", "admin_notes", "reviewed_at", "reviewed_by", "created_at"
    )} | ({"author_username": author_username} if author_username else {})


@router.post("/problem-submissions", status_code=201)
def submit_problem(data: ProblemSubmissionCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(f"problem-submit:{user.id}", 5)
    slug = slugify(data.title)
    # Ensure unique slug by appending a short random suffix
    import secrets as _secrets
    slug = f"{slug}-{_secrets.token_hex(3)}"
    sub = ProblemSubmission(author_id=user.id, slug=slug, **data.model_dump())
    db.add(sub)
    db.commit()
    return submission_problem_view(sub)


@router.get("/problem-submissions")
def my_problem_submissions(page: int = Query(1, ge=1), user: User = Depends(current_user), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count()).select_from(ProblemSubmission).where(ProblemSubmission.author_id == user.id))
    rows = db.scalars(select(ProblemSubmission).where(ProblemSubmission.author_id == user.id)
                      .order_by(ProblemSubmission.created_at.desc()).offset((page - 1) * 20).limit(20))
    return {"items": [submission_problem_view(row) for row in rows], "total": total, "page": page, "limit": 20}


# ── admin endpoints ───────────────────────────────────────

@router.get("/admin/problem-submissions")
def admin_list_submissions(status_filter: str = Query("", alias="status"), page: int = Query(1, ge=1),
                           admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    query = select(ProblemSubmission)
    if status_filter:
        query = query.where(ProblemSubmission.status == status_filter)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.execute(select(ProblemSubmission, User.username)
                      .join(User, ProblemSubmission.author_id == User.id)
                      .where(*([ProblemSubmission.status == status_filter] if status_filter else []))
                      .order_by(ProblemSubmission.created_at.desc())
                      .offset((page - 1) * 20).limit(20))
    return {"items": [submission_problem_view(sub, username) for sub, username in rows],
            "total": total, "page": page, "limit": 20}


@router.get("/admin/problem-submissions/{submission_id}")
def admin_get_submission(submission_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.execute(select(ProblemSubmission, User.username)
                     .join(User, ProblemSubmission.author_id == User.id)
                     .where(ProblemSubmission.id == submission_id)).first()
    if not row:
        raise HTTPException(404, "Submission not found.")
    sub, username = row
    return submission_problem_view(sub, username)


@router.patch("/admin/problem-submissions/{submission_id}")
def admin_review_submission(submission_id: str, data: AdminReviewAction,
                            admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    sub = db.get(ProblemSubmission, submission_id)
    if not sub:
        raise HTTPException(404, "Submission not found.")
    sub.status = data.action
    sub.admin_notes = data.admin_notes
    sub.reviewed_at = now()
    sub.reviewed_by = admin.id
    db.commit()
    return submission_problem_view(sub)


@router.get("/robots.txt", response_class=PlainTextResponse)
def api_robots_txt():
    return PlainTextResponse(generate_robots_txt(), media_type="text/plain")


@router.get("/sitemap.xml", response_class=Response)
def api_sitemap_xml():
    return Response(content=generate_sitemap_xml(), media_type="application/xml")

