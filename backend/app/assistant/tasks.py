"""Assistant worker task. The transient request payload (current code) is always cleared."""
import logging

from sqlalchemy import update

from app.celery_app import celery
from app.db import open_session
from app.models import AIInteraction, now

log = logging.getLogger(__name__)


@celery.task(name="app.assistant.respond")
def assistant_task(interaction_id: str):
    with open_session() as db:
        claimed = db.execute(update(AIInteraction).where(AIInteraction.id == interaction_id,
                                                         AIInteraction.status == "queued").values(status="running"))
        db.commit()
        if not claimed.rowcount:
            return
        interaction = db.get(AIInteraction, interaction_id)
        try:
            from app.assistant.service import respond
            respond(db, interaction)
            interaction.status = "completed"
        except Exception:
            db.rollback()
            interaction = db.get(AIInteraction, interaction_id)
            log.exception("Assistant request failed: %s", interaction_id)
            interaction.status = "error"
            interaction.error = "The assistant could not answer this request. Manual debugging is unaffected; please try again."
        interaction.payload = None
        interaction.completed_at = now()
        db.commit()
