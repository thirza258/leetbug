import time
from datetime import timedelta
from types import SimpleNamespace

from docker.errors import NotFound

from app import tasks
from app.models import Hint, Submission, now


def test_cleanup_expires_abandoned_jobs_and_containers(client, member, db_factory, monkeypatch):
    with db_factory() as db:
        old = Submission(user_id=member["id"], problem_id=1, language="python", mode="manual", code="source",
                         status="running", created_at=now() - timedelta(minutes=6))
        current = Submission(user_id=member["id"], problem_id=1, language="python", mode="manual", code="source", status="queued")
        hint = Hint(user_id=member["id"], problem_id=1, language="python", level=1,
                    status="queued", created_at=now() - timedelta(minutes=6))
        db.add_all([old, current, hint])
        db.commit()
        old_id, current_id, hint_id = old.id, current.id, hint.id

    removed, closed = [], []
    def gone(**kwargs):
        raise NotFound("Already removed by the evaluation worker")
    containers = [
        SimpleNamespace(labels={"expires_at": str(time.time() - 1)}, remove=gone),
        SimpleNamespace(labels={"expires_at": str(time.time() - 1)}, remove=lambda **kwargs: removed.append("expired")),
        SimpleNamespace(labels={"expires_at": str(time.time() + 60)}, remove=lambda **kwargs: removed.append("active")),
    ]
    def listing(**kwargs):
        assert kwargs == {"all": True, "filters": {"label": "app=leetbug-sandbox"}}
        return containers
    docker_client = SimpleNamespace(containers=SimpleNamespace(list=listing), close=lambda: closed.append(True))
    monkeypatch.setattr(tasks.docker, "DockerClient", lambda **kwargs: docker_client)
    tasks.cleanup()

    with db_factory() as db:
        assert db.get(Submission, old_id).status == "error"
        assert db.get(Submission, current_id).status == "queued"
        assert db.get(Hint, hint_id).status == "error"
    assert removed == ["expired"] and closed == [True]
