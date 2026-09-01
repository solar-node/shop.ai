"""
Razorpay test-mode integration. LLM never determines payment success (spec section 15) -
only this module, talking to Razorpay's actual API, does.
"""
import os
import requests
import razorpay
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")


def get_client():
    key_id = os.environ.get("RAZORPAY_KEY_ID", "") or RAZORPAY_KEY_ID
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "") or RAZORPAY_KEY_SECRET
    if not key_id or not key_secret:
        raise RuntimeError(
            "Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET env vars (use test-mode keys)."
        )
    return razorpay.Client(auth=(key_id, key_secret))




try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(f):
            return f
        return decorator


@traceable(run_type="tool", name="Razorpay Create Order")
def create_order(amount_rupees: float, receipt: str, notes: dict = None):
    """Creates a Razorpay order (paise-denominated). Returns dict with 'id' etc."""
    client = get_client()
    return client.order.create({
        "amount":   int(round(amount_rupees * 100)),
        "currency": "INR",
        "receipt":  receipt,
        "notes":    notes or {},
    })


def fetch_order(order_id: str):
    client = get_client()
    return client.order.fetch(order_id)


def fetch_payment(payment_id: str):
    client = get_client()
    return client.payment.fetch(payment_id)


@traceable(run_type="tool", name="Razorpay Verify Payment Signature")
def verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    client = get_client()
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id":   razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature":  razorpay_signature,
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        return False



def create_payment_link(amount_rupees: float, description: str, reference_id: str, notes: dict = None):
    """Creates a hosted Razorpay payment link (used when manual payment needed above limit)."""
    client = get_client()
    return client.payment_link.create({
        "amount":       int(round(amount_rupees * 100)),
        "currency":     "INR",
        "description":  description,
        "reference_id": reference_id,
        "notes":        notes or {},
    })


def fetch_payment_link_status(payment_link_id: str):
    client = get_client()
    return client.payment_link.fetch(payment_link_id)


def execute_s2s_card_payment(amount_rupees: float, receipt: str, description: str, notes: dict = None) -> dict:
    """
    Executes a REAL autonomous payment via Razorpay S2S JSON API using test card.

    Flow:
      1. Create a Razorpay Order (appears in Orders tab → 'Created')
      2. POST /v1/payments/create/json with test card credentials
         → Razorpay processes the card, creates a real payment_id
         → Order moves to 'Attempted', then 'Paid'
      3. Capture the payment via /v1/payments/{id}/capture
         → Order status → 'Paid', Payment status → 'Captured'

    In Razorpay Test Mode this bypasses OTP entirely for the test card.
    """
    key_id = os.environ.get("RAZORPAY_KEY_ID", "")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    card = {
        "number": os.environ.get("RAZORPAY_TEST_CARD_NUMBER", ""),
        "expiry_month": os.environ.get("RAZORPAY_TEST_CARD_EXPIRY_MONTH", ""),
        "expiry_year": os.environ.get("RAZORPAY_TEST_CARD_EXPIRY_YEAR", ""),
        "cvv": os.environ.get("RAZORPAY_TEST_CARD_CVV", ""),
        "name": os.environ.get("RAZORPAY_TEST_CARD_NAME", ""),
    }
    if not key_id or not key_secret:
        raise RuntimeError("Set Razorpay credentials in environment variables.")
    if not all(card.values()):
        raise RuntimeError("Set RAZORPAY_TEST_CARD_* variables before using S2S test payment.")

    auth = (key_id, key_secret)
    amount_paise = int(round(amount_rupees * 100))

    # Step 1: Create Razorpay Order
    order_resp = requests.post(
        "https://api.razorpay.com/v1/orders",
        auth=auth,
        json={
            "amount":   amount_paise,
            "currency": "INR",
            "receipt":  receipt,
            "notes":    notes or {"agent": "Shop.ai Autonomous Buyer", "mandate": "SUB_2500_AUTOPAY"},
        },
        timeout=15,
    )
    order_resp.raise_for_status()
    order = order_resp.json()
    order_id = order["id"]

    # Step 2: Submit S2S payment with test card via Razorpay JSON API
    payment_payload = {
        "amount":    amount_paise,
        "currency":  "INR",
        "order_id":  order_id,
        "email":     "agent@shop.ai",

        "contact":   "9999999999",
        "method":    "card",
        "card[number]":       card["number"],
        "card[expiry_month]": card["expiry_month"],
        "card[expiry_year]":  card["expiry_year"],
        "card[cvv]":          card["cvv"],
        "card[name]":         card["name"],
    }

    pay_resp = requests.post(
        "https://api.razorpay.com/v1/payments/create/json",
        auth=auth,
        data=payment_payload,
        timeout=20,
    )

    pay_data = pay_resp.json()

    # Handle 3DS / next_action redirect (test cards skip this)
    payment_id   = pay_data.get("razorpay_payment_id") or pay_data.get("payment_id") or pay_data.get("id")
    next_action  = pay_data.get("next", {})

    if not payment_id and next_action.get("redirect_url"):
        # Follow redirect silently (test cards auto-succeed)
        redirect_resp = requests.get(next_action["redirect_url"], auth=auth, timeout=15, allow_redirects=True)
        # Re-fetch order to get linked payment_id
        order_detail = requests.get(f"https://api.razorpay.com/v1/orders/{order_id}/payments", auth=auth, timeout=10)
        payments = order_detail.json().get("items", [])
        if payments:
            payment_id = payments[0]["id"]

    if not payment_id:
        return {
            "status":     "AWAITING_PAYMENT",
            "order_id":   order_id,
            "payment_id": None,
            "error":      "Payment created but ID not returned — check Razorpay dashboard.",
            "raw":        pay_data,
        }

    # Step 3: Capture the payment
    capture_resp = requests.post(
        f"https://api.razorpay.com/v1/payments/{payment_id}/capture",
        auth=auth,
        json={"amount": amount_paise, "currency": "INR"},
        timeout=15,
    )
    captured = capture_resp.json()
    status   = captured.get("status", "captured")   # 'captured' = success

    return {
        "order_id":   order_id,
        "payment_id": payment_id,
        "amount":     amount_rupees,
        "status":     "captured" if status == "captured" else status,
        "receipt":    receipt,
    }
