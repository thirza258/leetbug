"""Organization API (PRD 9.7, Phase 6): company accounts, members, private assessment packs,
invitations, candidate reporting, comparison, exports and competency profiles.

Assessment configuration, publication, invitations and sessions reuse ``app.assessments`` — the
endpoints here only scope those records to an organization and enforce its roles.
"""
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.assessments import routes as assessment_routes
from app.auth import current_user, require_admin, utc
from app.db import get_db
from app.events import audit, record_event
from app.limits import rate_limit
from app.models import (
    Assessment,
    AssessmentInvitation,
    CompetencyProfile,
    Organization,
    OrganizationMember,
    User,
    now,
)
from app.organizations import access, analytics, service
from app.organizations.schemas import (
    ExpirationUpdate,
    InvitationUpdate,
    MemberCreate,
    MemberUpdate,
    OrganizationAssessmentCreate,
    OrganizationCreate,
    OrganizationUpdate,
    ProfileCreate,
    ProfileUpdate,
)

router = APIRouter(prefix="/api", tags=["organizations"])


def limit_writes(user) -> None:
    rate_limit(f"organization-write:{user.id}", 30)


# ── company accounts ──────────────────────────────────────────────────────────────────────


@router.post("/organizations", status_code=201)
def create_organization(data: OrganizationCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    rate_limit(f"organization-create:{user.id}", 5)
    org = service.create(db, user, data.name, data.slug)
    db.commit()
    return service.view(db, org, "owner")


@router.get("/organizations")
def my_organizations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Organization, OrganizationMember.role)
                      .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
                      .where(OrganizationMember.user_id == user.id).order_by(Organization.name))
    items = [service.view(db, org, role) for org, role in rows]
    return {"items": items, "total": len(items)}


@router.get("/organizations/{slug}")
def organization_detail(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    org, role = service.load(db, slug, user)
    return service.view(db, org, role)


@router.patch("/organizations/{slug}")
def rename_organization(slug: str, data: OrganizationUpdate, user: User = Depends(current_user),
                        db: Session = Depends(get_db)):
    limit_writes(user)
    org, role = service.load(db, slug, user, manage=True)
    if org.name != data.name:
        audit(db, user.id, "organization.renamed", "organization", org.id, before=org.name, after=data.name)
        org.name = data.name
        db.commit()
    return service.view(db, org, role)


# ── membership ────────────────────────────────────────────────────────────────────────────


@router.get("/organizations/{slug}/members")
def list_members(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    org, _ = service.load(db, slug, user)
    items = service.member_rows(db, org)
    return {"items": items, "total": len(items)}


@router.post("/organizations/{slug}/members", status_code=201)
def add_member(slug: str, data: MemberCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit_writes(user)
    org, role = service.load(db, slug, user, manage=True)
    member = service.add_member(db, org, user, role, str(data.email), data.role)
    db.commit()
    return member


@router.patch("/organizations/{slug}/members/{user_id}")
def change_member_role(slug: str, user_id: str, data: MemberUpdate, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    limit_writes(user)
    org, role = service.load(db, slug, user, manage=True)
    result = service.change_role(db, org, user, role, user_id, data.role)
    db.commit()
    return result


@router.delete("/organizations/{slug}/members/{user_id}", status_code=204)
def remove_member(slug: str, user_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit_writes(user)
    org, role = service.load(db, slug, user)
    service.remove_member(db, org, user, role, user_id)
    db.commit()


# ── private assessment packs ──────────────────────────────────────────────────────────────


@router.get("/organizations/{slug}/assessments")
def organization_assessments(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    org, _ = service.load(db, slug, user)
    rows = db.scalars(select(Assessment).where(Assessment.organization_id == org.id)
                      .order_by(Assessment.created_at.desc(), Assessment.title))
    items = [assessment_routes.admin_view(db, row) for row in rows]
    return {"items": items, "total": len(items)}


@router.post("/organizations/{slug}/assessments", status_code=201)
def create_organization_assessment(slug: str, data: OrganizationAssessmentCreate,
                                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit_writes(user)
    org, _ = service.load(db, slug, user, manage=True)
    # The assessment feature validates, audits and stores it; this endpoint only scopes it to the org.
    return assessment_routes.admin_create(data.model_copy(update={"organization_id": org.id}), user=user, db=db)


@router.patch("/organizations/{slug}/assessments/{assessment_id}/expiration")
def update_assessment_expiration(slug: str, assessment_id: str, data: ExpirationUpdate,
                                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    limit_writes(user)
    org, _ = service.load(db, slug, user, manage=True)
    assessment = service.org_assessment(db, org, assessment_id)
    service.update_expiration(db, user, assessment, data.available_until)
    db.commit()
    return assessment_routes.admin_view(db, assessment)


@router.get("/organizations/{slug}/assessments/{assessment_id}/export")
def export_assessment(slug: str, assessment_id: str, format: Literal["csv", "json"] = "csv",
                      user: User = Depends(current_user), db: Session = Depends(get_db)):
    org, _ = service.load(db, slug, user)
    assessment = service.org_assessment(db, org, assessment_id)
    body, media_type = analytics.export(db, org, assessment, format)
    record_event(db, "organization.results_exported", user_id=user.id, organization_id=org.id,
                 assessment_id=assessment.id, format=format)
    db.commit()
    return Response(content=body, media_type=media_type, headers={
        "Content-Disposition": f'attachment; filename="{org.slug}-{assessment.slug}-results.{format}"'})


# ── invitations ───────────────────────────────────────────────────────────────────────────


def invitation_view(row: AssessmentInvitation, assessment: Assessment) -> dict:
    return {"id": row.id, "assessment_id": assessment.id, "assessment_slug": assessment.slug,
            "assessment_title": assessment.title, "email": row.email, "status": service.invitation_status(row),
            "created_at": service.iso(row.created_at), "expires_at": service.iso(row.expires_at),
            "accepted_at": service.iso(row.accepted_at)}


def org_invitation(db, org: Organization, invitation_id: str) -> tuple[AssessmentInvitation, Assessment]:
    row = db.get(AssessmentInvitation, invitation_id)
    assessment = db.get(Assessment, row.assessment_id) if row else None
    if row is None or assessment is None or assessment.organization_id != org.id:
        raise HTTPException(404, "Invitation not found.")
    return row, assessment


@router.get("/organizations/{slug}/invitations")
def organization_invitations(slug: str, assessment_id: str | None = None, user: User = Depends(current_user),
                             db: Session = Depends(get_db)):
    org, _ = service.load(db, slug, user)
    query = (select(AssessmentInvitation, Assessment)
             .join(Assessment, AssessmentInvitation.assessment_id == Assessment.id)
             .where(Assessment.organization_id == org.id))
    if assessment_id:
        query = query.where(Assessment.id == assessment_id)
    items = [invitation_view(row, assessment)
             for row, assessment in db.execute(query.order_by(AssessmentInvitation.created_at.desc()))]
    summary: dict[str, int] = {}
    for item in items:
        summary[item["status"]] = summary.get(item["status"], 0) + 1
    return {"items": items, "total": len(items), "status_counts": summary}


@router.patch("/organizations/{slug}/invitations/{invitation_id}")
def update_invitation(slug: str, invitation_id: str, data: InvitationUpdate, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    limit_writes(user)
    org, _ = service.load(db, slug, user, manage=True)
    row, assessment = org_invitation(db, org, invitation_id)
    if row.status in {"revoked", "accepted"}:
        raise HTTPException(409, f"An {row.status} invitation cannot be changed.")
    expires_at = data.expires_at if data.expires_at is not None else \
        max(now(), utc(row.expires_at) if row.expires_at else now()) + timedelta(days=data.extend_days)
    if utc(expires_at) <= now():
        raise HTTPException(422, "The new expiry must be in the future.")
    before = service.iso(row.expires_at)
    row.expires_at, row.status = expires_at, "pending"
    audit(db, user.id, "assessment.invitation_expiry_updated", "assessment_invitation", row.id,
          before=before, after=service.iso(expires_at))
    db.commit()
    return invitation_view(row, assessment)


@router.delete("/organizations/{slug}/invitations/{invitation_id}", status_code=204)
def revoke_invitation(slug: str, invitation_id: str, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    limit_writes(user)
    org, _ = service.load(db, slug, user, manage=True)
    row, _ = org_invitation(db, org, invitation_id)
    if row.status != "revoked":
        row.status = "revoked"
        audit(db, user.id, "assessment.invitation_revoked", "assessment_invitation", row.id, email=row.email)
        db.commit()


# ── candidate reporting ───────────────────────────────────────────────────────────────────


@router.get("/organizations/{slug}/candidates")
def organization_candidates(slug: str, assessment_id: str | None = None, user: User = Depends(current_user),
                            db: Session = Depends(get_db)):
    org, _ = service.load(db, slug, user)
    if assessment_id:
        service.org_assessment(db, org, assessment_id)
    items = analytics.candidates(db, org, assessment_id)
    return {"items": items, "total": len(items), "notes": [analytics.HIRING_CAVEAT]}


@router.get("/organizations/{slug}/analytics")
def organization_analytics(slug: str, assessment_id: str | None = None, user: User = Depends(current_user),
                           db: Session = Depends(get_db)):
    org, _ = service.load(db, slug, user)
    return analytics.analytics(db, org, assessment_id)


@router.get("/organizations/{slug}/compare")
def compare_candidates(slug: str, sessions: str = Query(min_length=3, max_length=400),
                       user: User = Depends(current_user), db: Session = Depends(get_db)):
    org, _ = service.load(db, slug, user)
    return analytics.compare(db, org, [value.strip() for value in sessions.split(",")])


# ── competency profiles ───────────────────────────────────────────────────────────────────


@router.get("/organizations/{slug}/competency-profiles")
def organization_profiles(slug: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    org, _ = service.load(db, slug, user)
    rows = db.scalars(select(CompetencyProfile).where(CompetencyProfile.organization_id == org.id)
                      .order_by(CompetencyProfile.name))
    items = [service.profile_view(db, row) for row in rows]
    return {"items": items, "total": len(items)}


@router.post("/organizations/{slug}/competency-profiles", status_code=201)
def create_organization_profile(slug: str, data: ProfileCreate, user: User = Depends(current_user),
                                db: Session = Depends(get_db)):
    limit_writes(user)
    org, _ = service.load(db, slug, user, manage=True)
    profile = service.create_profile(db, user, org.id, data)
    db.commit()
    return service.profile_view(db, profile)


@router.patch("/organizations/{slug}/competency-profiles/{profile_id}")
def update_organization_profile(slug: str, profile_id: str, data: ProfileUpdate, user: User = Depends(current_user),
                                db: Session = Depends(get_db)):
    limit_writes(user)
    org, _ = service.load(db, slug, user, manage=True)
    profile = service.update_profile(db, user, service.org_profile(db, org, profile_id), data)
    db.commit()
    return service.profile_view(db, profile)


@router.delete("/organizations/{slug}/competency-profiles/{profile_id}", status_code=204)
def delete_organization_profile(slug: str, profile_id: str, user: User = Depends(current_user),
                                db: Session = Depends(get_db)):
    limit_writes(user)
    org, _ = service.load(db, slug, user, manage=True)
    service.delete_profile(db, user, service.org_profile(db, org, profile_id))
    db.commit()


@router.get("/competency-profiles/global")
def global_profiles(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(CompetencyProfile).where(CompetencyProfile.organization_id.is_(None))
                      .order_by(CompetencyProfile.name))
    items = [service.profile_view(db, row) for row in rows]
    return {"items": items, "total": len(items)}


@router.post("/admin/competency-profiles", status_code=201)
def create_global_profile(data: ProfileCreate, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    limit_writes(admin)
    profile = service.create_profile(db, admin, None, data)
    db.commit()
    return service.profile_view(db, profile)


@router.get("/competency-profiles")
def available_profiles(organization_id: str | None = None, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """Profiles an assessment may use: global templates plus the organization's own (members only)."""
    query = select(CompetencyProfile).where(CompetencyProfile.organization_id.is_(None))
    if organization_id:
        if not access.can_review_org(db, user, organization_id):
            raise HTTPException(404, "Organization not found.")
        query = select(CompetencyProfile).where((CompetencyProfile.organization_id == organization_id)
                                                | CompetencyProfile.organization_id.is_(None))
    rows = db.scalars(query.order_by(CompetencyProfile.organization_id.is_(None), CompetencyProfile.name))
    items = [service.profile_view(db, row) for row in rows]
    return {"items": items, "total": len(items)}
