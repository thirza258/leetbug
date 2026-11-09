"""Insert-only seeding of the built-in assessment packs."""
from copy import deepcopy

from sqlalchemy import select

from app.assessments.catalog import ASSESSMENT_PACKS, DEFAULT_RUBRIC
from app.models import Assessment


def seed_assessments(db):
    existing = set(db.scalars(select(Assessment.slug)))
    for pack in ASSESSMENT_PACKS:
        if pack["slug"] in existing:
            continue
        db.add(Assessment(
            slug=pack["slug"], title=pack["title"], description=pack["description"],
            assessment_type=pack["assessment_type"], duration_seconds=pack["duration_seconds"],
            configuration=deepcopy(pack["configuration"]), scoring_rubric=deepcopy(DEFAULT_RUBRIC),
            assistance_policy=deepcopy(pack["assistance_policy"]), visibility="public", status="published",
        ))
    db.flush()
