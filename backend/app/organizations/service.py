"""Company accounts, membership rules and competency profiles (PRD 9.7, Phase 6).

Organization resources are invisible to non-members: every lookup that fails authorization reports
"not found" so slugs and candidate data never leak. Assessment logic stays in ``app.assessments``.
"""
import re

from fastapi import HTTPException
from sqlalchemy import func, select

from app.events import audit
from app.models import (
    Assessment,
    AssessmentSession,
    CompetencyProfile,
    Organization,
    OrganizationMember,
    User,
    now,
)
from app.organizations import access

RESERVED_SLUGS = {"new", "admin", "global", "api"}


def iso(value):
    from app.auth import utc
    return utc(value).isoformat() if value is not None else None


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:90]
    return slug if len(slug) >= 3 else f"org-{slug}".strip("-")


def unique_slug(db, model, base: str, **scope) -> str:
    slug, index = base, 2
    while slug in RESERVED_SLUGS or db.scalar(select(model.id).where(model.slug == slug, *[
            getattr(model, key) == value if value is not None else getattr(model, key).is_(None)
            for key, value in scope.items()])):
        slug, index = f"{base}-{index}", index + 1
    return slug


# ── organizations ─────────────────────────────────────────────────────────────────────────


def load(db, slug: str, user, *, manage: bool = False) -> tuple[Organization, str]:
    """The organization and the caller's effective role. Non-members get 404; read-only roles get 403
    for management actions."""
    org = db.scalar(select(Organization).where(Organization.slug == slug))
    role = access.effective_role(db, user, org.id) if org is not None else None
    if org is None or role is None:
        raise HTTPException(404, "Organization not found.")
    if manage and role not in access.MANAGER_ROLES:
        raise HTTPException(403, "Only organization owners and admins can do that.")
    return org, role


def counts(db, org: Organization) -> dict:
    return {
        "members": db.scalar(select(func.count()).select_from(OrganizationMember)
                             .where(OrganizationMember.organization_id == org.id)) or 0,
        "assessments": db.scalar(select(func.count()).select_from(Assessment)
                                 .where(Assessment.organization_id == org.id)) or 0,
        "finalized_sessions": db.scalar(
            select(func.count()).select_from(AssessmentSession).join(Assessment)
            .where(Assessment.organization_id == org.id, AssessmentSession.finalized_at.is_not(None))) or 0,
    }


def view(db, org: Organization, role: str) -> dict:
    return {"id": org.id, "slug": org.slug, "name": org.name, "role": role, "created_at": iso(org.created_at),
            "counts": counts(db, org),
            "permissions": {"manage": role in access.MANAGER_ROLES, "review": True,
                            "owner": role == "owner"}}


def create(db, user, name: str, slug: str | None) -> Organization:
    if slug and (slug in RESERVED_SLUGS or db.scalar(select(Organization.id).where(Organization.slug == slug))):
        raise HTTPException(409, "That organization slug is already in use.")
    org = Organization(name=name, slug=slug or unique_slug(db, Organization, slugify(name)), created_by=user.id)
    db.add(org)
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role="owner"))
    audit(db, user.id, "organization.created", "organization", org.id, slug=org.slug, name=name)
    return org


# ── membership ────────────────────────────────────────────────────────────────────────────


def owner_count(db, organization_id: str) -> int:
    return db.scalar(select(func.count()).select_from(OrganizationMember).where(
        OrganizationMember.organization_id == organization_id, OrganizationMember.role == "owner")) or 0


def member_rows(db, org: Organization) -> list[dict]:
    rows = db.execute(select(OrganizationMember, User).join(User, OrganizationMember.user_id == User.id)
                      .where(OrganizationMember.organization_id == org.id)
                      .order_by(OrganizationMember.created_at, User.username))
    order = {"owner": 0, "admin": 1, "reviewer": 2}
    items = [{"user_id": user.id, "username": user.username, "email": user.email, "role": member.role,
              "joined_at": iso(member.created_at)} for member, user in rows]
    return sorted(items, key=lambda row: (order.get(row["role"], 3), row["username"]))


def _require_owner_for(actor_role: str, *roles: str) -> None:
    if "owner" in roles and actor_role != "owner":
        raise HTTPException(403, "Only an owner can grant, change or remove the owner role.")


def add_member(db, org: Organization, actor, actor_role: str, email: str, role: str) -> dict:
    _require_owner_for(actor_role, role)
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None:
        raise HTTPException(404, "No LeetBug account uses that email. Ask them to register first.")
    if db.get(OrganizationMember, (org.id, user.id)) is not None:
        raise HTTPException(409, "That person is already a member.")
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, role=role))
    audit(db, actor.id, "organization.member_added", "organization", org.id, member_id=user.id, role=role)
    return {"user_id": user.id, "username": user.username, "email": user.email, "role": role}


def change_role(db, org: Organization, actor, actor_role: str, user_id: str, role: str) -> dict:
    member = db.get(OrganizationMember, (org.id, user_id))
    if member is None:
        raise HTTPException(404, "Member not found.")
    if member.role == role:
        return {"user_id": user_id, "role": role}
    _require_owner_for(actor_role, member.role, role)
    if member.role == "owner" and owner_count(db, org.id) <= 1:
        raise HTTPException(409, "An organization needs at least one owner. Promote another owner first.")
    previous, member.role = member.role, role
    audit(db, actor.id, "organization.member_role_changed", "organization", org.id, member_id=user_id,
          before=previous, after=role)
    return {"user_id": user_id, "role": role}


def remove_member(db, org: Organization, actor, actor_role: str | None, user_id: str) -> None:
    member = db.get(OrganizationMember, (org.id, user_id))
    if member is None:
        raise HTTPException(404, "Member not found.")
    leaving = actor.id == user_id
    if not leaving:
        if actor_role not in access.MANAGER_ROLES:
            raise HTTPException(403, "Only organization owners and admins can remove members.")
        _require_owner_for(actor_role, member.role)
    if member.role == "owner" and owner_count(db, org.id) <= 1:
        raise HTTPException(409, "An organization needs at least one owner. Promote another owner first.")
    db.delete(member)
    audit(db, actor.id, "organization.member_removed", "organization", org.id, member_id=user_id,
          role=member.role, left=leaving)


# ── competency profiles ───────────────────────────────────────────────────────────────────


def profile_view(db, profile: CompetencyProfile) -> dict:
    used_by = list(db.scalars(select(Assessment.id).where(Assessment.competency_profile_id == profile.id,
                                                          Assessment.status != "archived")))
    return {"id": profile.id, "organization_id": profile.organization_id, "slug": profile.slug,
            "name": profile.name, "description": profile.description, "weights": profile.weights or {},
            "scope": "organization" if profile.organization_id else "global",
            "assessments_using": len(used_by), "created_at": iso(profile.created_at)}


def org_profile(db, org: Organization, profile_id: str) -> CompetencyProfile:
    profile = db.get(CompetencyProfile, profile_id)
    if profile is None or profile.organization_id != org.id:
        raise HTTPException(404, "Competency profile not found.")
    return profile


def create_profile(db, actor, organization_id: str | None, data) -> CompetencyProfile:
    if data.slug and db.scalar(select(CompetencyProfile.id).where(
            CompetencyProfile.slug == data.slug,
            CompetencyProfile.organization_id == organization_id if organization_id
            else CompetencyProfile.organization_id.is_(None))):
        raise HTTPException(409, "That profile slug is already in use.")
    slug = data.slug or unique_slug(db, CompetencyProfile, slugify(data.name), organization_id=organization_id)
    profile = CompetencyProfile(organization_id=organization_id, slug=slug, name=data.name,
                                description=data.description, weights=data.weights, created_by=actor.id)
    db.add(profile)
    db.flush()
    audit(db, actor.id, "competency_profile.created", "competency_profile", profile.id,
          organization_id=organization_id, weights=data.weights)
    return profile


def update_profile(db, actor, profile: CompetencyProfile, data) -> CompetencyProfile:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in changes.items():
        setattr(profile, key, value)
    # Running and finished sessions keep the weights captured in their snapshots.
    audit(db, actor.id, "competency_profile.updated", "competency_profile", profile.id, fields=sorted(changes))
    return profile


def delete_profile(db, actor, profile: CompetencyProfile) -> None:
    in_use = db.scalar(select(func.count()).select_from(Assessment).where(
        Assessment.competency_profile_id == profile.id, Assessment.status != "archived")) or 0
    if in_use:
        raise HTTPException(409, f"{in_use} assessment(s) use this profile. Detach it or archive them first.")
    for assessment in db.scalars(select(Assessment).where(Assessment.competency_profile_id == profile.id)):
        assessment.competency_profile_id = None
    audit(db, actor.id, "competency_profile.deleted", "competency_profile", profile.id,
          organization_id=profile.organization_id, name=profile.name)
    db.delete(profile)


# ── assessments and sessions ──────────────────────────────────────────────────────────────


def org_assessment(db, org: Organization, assessment_id: str) -> Assessment:
    assessment = db.get(Assessment, assessment_id)
    if assessment is None or assessment.organization_id != org.id:
        raise HTTPException(404, "Assessment not found.")
    return assessment


def finalized_sessions(db, org: Organization, assessment_id: str | None = None) -> list[tuple]:
    """(session, assessment, candidate) for finalized sessions with a stored report."""
    query = (select(AssessmentSession, Assessment, User)
             .join(Assessment, AssessmentSession.assessment_id == Assessment.id)
             .join(User, AssessmentSession.user_id == User.id)
             .where(Assessment.organization_id == org.id, AssessmentSession.finalized_at.is_not(None),
                    AssessmentSession.report.is_not(None)))
    if assessment_id:
        query = query.where(Assessment.id == assessment_id)
    return list(db.execute(query.order_by(AssessmentSession.started_at)))


def update_expiration(db, actor, assessment: Assessment, available_until) -> None:
    from app.auth import utc
    if available_until is not None and assessment.available_from is not None and \
            utc(available_until) <= utc(assessment.available_from):
        raise HTTPException(422, "The assessment must close after it opens.")
    before = iso(assessment.available_until)
    # Scheduling only: the challenge configuration and its version stay unchanged.
    assessment.available_until = available_until
    audit(db, actor.id, "assessment.expiration_updated", "assessment", assessment.id,
          before=before, after=iso(available_until))


def invitation_status(row) -> str:
    from app.auth import utc
    if row.status == "pending" and row.expires_at is not None and utc(row.expires_at) <= now():
        return "expired"
    return row.status
