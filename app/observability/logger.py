"""Decision-ledger logging."""

import time
from contextlib import contextmanager

from database.models import AgentEvent


def log_event(db, session_id: str, agent: str, action: str,
              detail: dict = None, latency_ms: int = None, success: bool = True):
    event = AgentEvent(
        session_id=session_id, agent=agent, action=action,
        detail=detail or {}, latency_ms=latency_ms, success=success,
    )
    db.add(event)
    db.commit()
    return event


@contextmanager
def timed_event(db, session_id: str, agent: str, action: str):
    start = time.time()
    data = {"detail": {}, "success": True}
    try:
        yield data
    except Exception as error:
        data["success"] = False
        data["detail"]["error"] = str(error)
        raise
    finally:
        log_event(
            db, session_id, agent, action, data["detail"],
            int((time.time() - start) * 1000), data["success"]
        )


def get_session_ledger(db, session_id: str):
    return (
        db.query(AgentEvent)
        .filter_by(session_id=session_id)
        .order_by(AgentEvent.timestamp.asc())
        .all()
    )
