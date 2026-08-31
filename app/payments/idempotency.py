"""
Payment idempotency. Never create a second payment for the same cart on retry/timeout -
always look up existing state first (spec section 16).
"""
from datetime import datetime
from database.models import Payment
from app.payments import razorpay_client as rzp


def get_idempotency_key(session_id: str, cart_id: str) -> str:
    return f"{session_id}:{cart_id}"


def create_or_get_payment(db, session_id: str, cart_id: str, amount: float, description: str):
    """
    Safe payment creation:
      1. Check if a payment already exists for this idempotency key.
      2. If yes and it's in a terminal or pending state, return it (never double-create).
      3. If no, create a new Razorpay payment link and persist it.
    """
    key = get_idempotency_key(session_id, cart_id)
    existing = db.query(Payment).filter_by(idempotency_key=key).first()
    if existing:
        return reconcile_payment(db, existing)

    link = rzp.create_payment_link(amount, description, reference_id=cart_id, notes={"session_id": session_id})
    payment = Payment(
        cart_id=cart_id,
        idempotency_key=key,
        razorpay_order_id=link["id"],  # payment_link id used as the tracked reference
        amount=amount,
        status="PENDING",
    )
    db.add(payment)
    db.commit()
    payment._payment_link_url = link.get("short_url")  # not persisted, just for immediate use
    return payment


def reconcile_payment(db, payment: Payment):
    """
    On timeout/unknown state, look up the actual status from Razorpay rather than guessing
    or retrying blindly (spec section 16: UNKNOWN -> reconcile).
    """
    if payment.status in ("SUCCESS", "FAILED"):
        return payment
    try:
        remote = rzp.fetch_payment_link_status(payment.razorpay_order_id)
        remote_status = remote.get("status")  # created, paid, expired, cancelled
        if remote_status == "paid":
            payment.status = "SUCCESS"
        elif remote_status in ("expired", "cancelled"):
            payment.status = "FAILED"
        else:
            payment.status = "PENDING"
    except Exception:
        payment.status = "UNKNOWN"
    payment.updated_at = datetime.utcnow()
    db.commit()
    return payment
