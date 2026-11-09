"""Insert-only seeding of the bundled incident catalog (PRD Phase 4).

Catalog incident ``n`` (1-based) becomes Incident ``n`` and Problem ``100000 + n`` — a range the
practice catalog never reaches — so appending incidents never moves existing IDs or progress.
Existing rows are never overwritten.
"""
import logging

from sqlalchemy import select

from app.incidents import catalog, validation
from app.incidents.service import incident_fields, problem_fields
from app.models import Incident, Problem

log = logging.getLogger(__name__)
PROBLEM_ID_BASE = 100000


def seed_incidents(db):
    # Read the attribute at call time so tests can substitute the catalog.
    for index, item in enumerate(catalog.INCIDENTS, 1):
        slug = item["slug"]
        if db.scalar(select(Incident.id).where(Incident.slug == slug)):
            continue
        fields = problem_fields(item)
        problem = db.scalar(select(Problem).where(Problem.slug == fields["slug"]))
        if problem is None:
            problem_id = PROBLEM_ID_BASE + index
            if db.get(Problem, problem_id) is not None:
                log.warning("Skipping incident %s: problem ID %s is already used", slug, problem_id)
                continue
            problem = Problem(id=problem_id, content_hash=validation.content_hash(fields), **fields)
            db.add(problem)
            db.flush()
        if db.get(Incident, index) is not None:
            log.warning("Skipping incident %s: incident ID %s is already used", slug, index)
            continue
        db.add(Incident(id=index, problem_id=problem.id, status="published", version=1, **incident_fields(item)))
        db.flush()
