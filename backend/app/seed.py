from sqlalchemy import select

from app.assessments.seed import seed_assessments
from app.auth import passwords
from app.catalog import CATALOG
from app.config import settings
from app.db import SessionLocal
from app.incidents.seed import seed_incidents
from app.models import Problem, User


def seed():
    with SessionLocal() as db:
        for index, item in enumerate(CATALOG, 1):
            if not db.scalar(select(Problem).where(Problem.slug == item["slug"])):
                db.add(Problem(id=index, **item))
        if settings.seed_demo_user and not db.scalar(select(User).where(User.email == "demo@leetbug.dev")):
            db.add(User(email="demo@leetbug.dev", username="demo_debugger",
                        password_hash=passwords.hash(settings.demo_password)))
        db.commit()
        # Insert-only: incident scenarios (problem IDs from 100001) and assessment packs.
        seed_incidents(db)
        db.commit()
        seed_assessments(db)
        db.commit()


if __name__ == "__main__":
    seed()

