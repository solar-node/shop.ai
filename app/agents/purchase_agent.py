"""Deterministic checkout agent. It executes the product selected by the orchestrator."""

from database.models import Payment, get_engine, get_session_factory
from app.mcp.client import merchant_client
from app.payments.idempotency import create_or_get_payment, reconcile_payment

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(f):
            return f
        return decorator

_engine = get_engine()

_Session = get_session_factory(_engine)


def _reserve_cart(session_id: str, product_id: str, price: float) -> dict:
    reservation = merchant_client.call(
        "reserve_inventory_tool", product_id=product_id, session_id=session_id, qty=1
    )
    if reservation.get("status") != "RESERVED":
        return {"status": "FAILED", "stage": "RESERVATION", "detail": reservation}

    cart = merchant_client.call("create_cart", session_id=session_id)
    merchant_client.call(
        "add_to_cart", cart_id=cart["cart_id"], product_id=product_id,
        qty=1, agreed_price=price
    )
    return {"reservation_id": reservation["reservation_id"], "cart_id": cart["cart_id"]}


def reserve_and_checkout(session_id: str, product_id: str, effective_price: float) -> dict:
    """Reserve inventory and create a payment through the idempotency layer."""
    checkout = _reserve_cart(session_id, product_id, effective_price)
    if checkout.get("status") == "FAILED":
        return checkout

    db = _Session()
    try:
        payment = create_or_get_payment(
            db, session_id=session_id, cart_id=checkout["cart_id"],
            amount=effective_price, description=f"Shop.ai order for {product_id}",
        )
        return {
            "status": "AWAITING_PAYMENT",
            **checkout,
            "payment_id": payment.id,
            "razorpay_order_id": payment.razorpay_order_id,
            "payment_link_url": getattr(payment, "_payment_link_url", None),
        }
    finally:
        db.close()


@traceable(run_type="tool", name="Prepare Checkout & Stock Lock")
def prepare_checkout(session_id: str, product_id: str, effective_price: float) -> dict:
    """Reserve stock, add the product to a cart, and create a Razorpay order."""

    checkout = _reserve_cart(session_id, product_id, effective_price)
    if checkout.get("status") == "FAILED":
        return checkout

    db = _Session()
    try:
        from app.payments.razorpay_client import create_order
        order = create_order(
            amount_rupees=effective_price,
            receipt=checkout["cart_id"],
            notes={"session_id": session_id, "product_id": product_id, "agent": "Shop.ai"},
        )

        payment = Payment(
            cart_id=checkout["cart_id"],
            idempotency_key=f"{session_id}:{checkout['cart_id']}",
            razorpay_order_id=order["id"],
            amount=effective_price,
            status="PENDING",
        )
        db.add(payment)
        db.commit()
        return {
            "status": "AWAITING_PAYMENT",
            **checkout,
            "payment_id": payment.id,
            "razorpay_order_id": order["id"],
            "amount": effective_price,
            "mode": "CHECKOUT_MODAL",
        }
    finally:
        db.close()


def check_and_finalize_payment(payment_id: str, reservation_id: str, cart_id: str) -> dict:
    """Reconcile payment with Razorpay and confirm or release the reservation."""
    db = _Session()
    try:
        payment = db.query(Payment).filter_by(id=payment_id).first()
        if not payment:
            return {"status": "UNKNOWN", "reason": "Payment not found."}

        payment = reconcile_payment(db, payment)

        if payment.status == "SUCCESS":
            order = merchant_client.call(
                "create_order_tool", cart_id=cart_id, payment_id=payment.id,
                total_amount=payment.amount,
            )
            return {"status": "SUCCESS", "order": order}

        if payment.status == "FAILED":
            merchant_client.call("release_inventory_tool", reservation_id=reservation_id)
            return {"status": "FAILED", "reason": "Payment failed or expired."}

        return {"status": payment.status}
    finally:
        db.close()
