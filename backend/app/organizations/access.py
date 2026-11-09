"""Organization roles (PRD 9.7, Phase 6).

Interface (used by ``app.assessments.access``):
    member_role(db, user_id, organization_id) -> "owner" | "admin" | "reviewer" | None
    can_manage_org(db, user, organization_id) -> bool      # owner or admin, or platform admin
    can_review_org(db, user, organization_id) -> bool      # any member role, or platform admin

Every role may read candidate data (reviewer is the least privileged role); only owners and
admins change members, assessments, invitations and competency profiles.
"""
from app.models import OrganizationMember
from app.policy import is_admin

ROLES = ("owner", "admin", "reviewer")
MANAGER_ROLES = frozenset({"owner", "admin"})


def member_role(db, user_id, organization_id):
    if not user_id or not organization_id:
        return None
    row = db.get(OrganizationMember, (organization_id, user_id))
    return row.role if row is not None and row.role in ROLES else None


def can_manage_org(db, user, organization_id) -> bool:
    if user is None or not organization_id:
        return False
    return is_admin(user) or member_role(db, user.id, organization_id) in MANAGER_ROLES


def can_review_org(db, user, organization_id) -> bool:
    if user is None or not organization_id:
        return False
    return is_admin(user) or member_role(db, user.id, organization_id) is not None


def effective_role(db, user, organization_id) -> str | None:
    """The member's role; platform administrators who are not members act as owners."""
    role = member_role(db, user.id, organization_id) if user is not None else None
    if role is None and is_admin(user):
        return "owner"
    return role
