"""Who may see, start, manage and review assessments (PRD 9.8, 9.9, 13.2).

All assessment authorization lives here so the organizations feature can extend it in one place.
Organization roles come from ``app.organizations.access``.
"""
from sqlalchemy import select

from app.auth import utc
from app.models import Assessment, AssessmentInvitation, AssessmentSession, Organization, now
from app.organizations import access as org_access
from app.policy import is_admin


def visibility_error(organization_id: str | None, visibility: str) -> str | None:
    """Organization packs are private (PRD 9.7): any signed-in user can create an organization, so an
    organization assessment must never appear in the public catalog."""
    if organization_id and visibility == "public":
        return "Organization assessments are private or invitation-only."
    return None


def can_create(db, user, organization_id: str | None) -> bool:
    if user is None:
        return False
    if organization_id:
        return db.get(Organization, organization_id) is not None and \
            org_access.can_manage_org(db, user, organization_id)
    return is_admin(user)


def can_manage(db, user, assessment: Assessment) -> bool:
    """Edit, publish, invite, review sessions and correct results."""
    if user is None:
        return False
    if is_admin(user):
        return True
    return bool(assessment.organization_id and org_access.can_manage_org(db, user, assessment.organization_id))


def can_review(db, user, assessment: Assessment) -> bool:
    """Read candidate sessions and full reports (organization reviewers included)."""
    if can_manage(db, user, assessment):
        return True
    return bool(user and assessment.organization_id
                and org_access.can_review_org(db, user, assessment.organization_id))


def is_org_member(db, user, assessment: Assessment) -> bool:
    return bool(user and assessment.organization_id
                and org_access.member_role(db, user.id, assessment.organization_id) is not None)


def invitation_for(db, user, assessment: Assessment) -> AssessmentInvitation | None:
    """A usable invitation for this user: matching email, not revoked/expired, not used by someone else."""
    if user is None:
        return None
    rows = db.scalars(select(AssessmentInvitation).where(
        AssessmentInvitation.assessment_id == assessment.id,
        AssessmentInvitation.email == user.email.lower(),
        AssessmentInvitation.status.in_(["pending", "accepted"])).order_by(AssessmentInvitation.created_at.desc()))
    for row in rows:
        if row.status == "accepted" and row.accepted_by not in (None, user.id):
            continue
        if row.status == "pending" and row.expires_at is not None and utc(row.expires_at) <= now():
            continue
        return row
    return None


def can_view(db, user, assessment: Assessment) -> bool:
    if can_review(db, user, assessment):
        return True
    if assessment.status != "published":
        return False
    if assessment.visibility == "public":
        return True
    if assessment.visibility == "private" and is_org_member(db, user, assessment):
        return True
    return invitation_for(db, user, assessment) is not None


def start_denial(db, user, assessment: Assessment) -> str | None:
    """Why this user cannot start a session (None when allowed). Admins may start any for preview."""
    if user is None:
        return "Sign in to start an assessment."
    if assessment.status != "published":
        return "This assessment is not open."
    if can_manage(db, user, assessment):
        return None
    if assessment.visibility == "invitation" or (assessment.visibility == "private"
                                                 and not is_org_member(db, user, assessment)):
        if invitation_for(db, user, assessment) is None:
            return "This assessment requires an invitation for your email address."
    return None


def session_viewer(db, user, session: AssessmentSession, assessment: Assessment) -> str | None:
    """"candidate", "reviewer", or None when the user may not see this session."""
    if user is None:
        return None
    if session.user_id == user.id:
        return "candidate"
    if can_review(db, user, assessment):
        return "reviewer"
    return None
