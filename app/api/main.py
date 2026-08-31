"""BudBuy REST API."""

import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv()

from app.agents.orchestrator import Orchestrator
from app.observability.logger import get_session_ledger
from app.payments.razorpay_client import verify_payment_signature
from database.models import AgentSession, get_engine, get_session_factory

app = FastAPI(title="BudBuy API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

_Session = get_session_factory(get_engine())
_sessions = {}


class RunRequest(BaseModel):
    goal: str
    simulate_oos: bool = False
    simulate_payment_timeout: bool = False


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def _get_or_restore(session_id: str) -> Orchestrator:
    if session_id in _sessions:
        return _sessions[session_id]

    db = _Session()
    try:
        record = db.query(AgentSession).filter_by(id=session_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Session not found.")
        orch = Orchestrator(session_id, record.user_goal or "")
        if record.state:
            orch.state = record.state
        _sessions[session_id] = orch
        return orch
    finally:
        db.close()


def _json(data: dict) -> dict:
    try:
        return json.loads(json.dumps(data, default=str))
    except Exception:
        return {"status": data.get("status", "FAILED"),
                "message_to_user": str(data.get("message_to_user", ""))}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "budbuy-api"}


@app.get("/api/status")
def status():
    return {
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
        "razorpay_live": bool(os.getenv("RAZORPAY_KEY_ID") and os.getenv("RAZORPAY_KEY_SECRET")),
        "serpapi_live": bool(os.getenv("SERPAPI_KEY")),
    }


@app.get("/api/config")
def config():
    return {"razorpay_key_id": os.getenv("RAZORPAY_KEY_ID", "")}


@app.post("/api/session")
def create_session():
    return {"session_id": f"ui_{uuid.uuid4().hex[:10]}"}


@app.post("/api/session/{session_id}/run")
def run_session(session_id: str, body: RunRequest):
    orch = Orchestrator(session_id, body.goal)
    _sessions[session_id] = orch
    try:
        return _json(orch.run(body.simulate_oos, body.simulate_payment_timeout))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/api/session/{session_id}/confirm")
def confirm_session(session_id: str):
    try:
        return _json(_get_or_restore(session_id).confirm_pending_purchase())
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/api/session/{session_id}/poll")
def poll_session_payment(session_id: str):
    try:
        return _json(_get_or_restore(session_id).poll_payment())
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/api/session/{session_id}/state")
def get_state(session_id: str):
    if session_id in _sessions:
        orch = _sessions[session_id]
        return {
            "session_id": session_id,
            "status": orch.state.get("status", "PROCESSING"),
            "state": _json(orch.state),
        }

    db = _Session()
    try:
        record = db.query(AgentSession).filter_by(id=session_id).first()
        if not record:
            return {"status": "NOT_FOUND"}
        return {"session_id": record.id, "status": record.status, "state": record.state}
    finally:
        db.close()


@app.get("/api/session/{session_id}/ledger")
def get_ledger(session_id: str):
    db = _Session()
    try:
        events = get_session_ledger(db, session_id)
        return {"events": [{
            "id": e.id, "agent": e.agent, "action": e.action,
            "detail": e.detail,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "latency_ms": e.latency_ms, "success": e.success,
        } for e in events]}
    finally:
        db.close()


@app.post("/api/session/{session_id}/verify_payment")
def verify_payment(session_id: str, body: VerifyPaymentRequest):
    if not verify_payment_signature(
        body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature
    ):
        raise HTTPException(status_code=400, detail="Invalid Razorpay payment signature.")

    orch = _get_or_restore(session_id)
    db = _Session()
    try:
        from database.models import Payment
        payment = db.query(Payment).filter_by(
            razorpay_order_id=body.razorpay_order_id
        ).first()
        if payment:
            payment.status = "SUCCESS"
            db.commit()
        orch.state.update({"status": "COMPLETED", "payment_status": "SUCCESS"})
        orch._finish("Payment confirmed! Order placed successfully.")
        return _json(orch.state)
    finally:
        db.close()
