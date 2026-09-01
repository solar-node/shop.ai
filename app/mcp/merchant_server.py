"""
Merchant MCP Server. Deterministic - NO LLM inside (spec section 18).
Represents "the merchant side" that the Buyer Agent (MCP client) negotiates with.
Run standalone for testing: python app/mcp/merchant_server.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from mcp.server.fastmcp import FastMCP
from database.models import (
    get_engine, get_session_factory, init_db,
    Product, Merchant, Inventory, Offer, Cart, CartItem, Order, Payment
)
from app.inventory.reservation import reserve_inventory, release_inventory, confirm_reservation, ReservationError


engine = init_db()
SessionLocal = get_session_factory(engine)

mcp = FastMCP("shopai-merchant")



def _db():
    return SessionLocal()


# ---------- PRODUCTS ----------

@mcp.tool()
def search_products(category: str = "", brand: str = "", max_price: float = 0,
                     query_text: str = "") -> str:
    """Search the merchant catalog by category, brand, and/or max price."""
    db = _db()
    try:
        q = db.query(Product)
        if category:
            q = q.filter(Product.category.ilike(f"%{category}%"))
        if brand:
            q = q.filter(Product.brand.ilike(f"%{brand}%"))
        if max_price:
            q = q.filter(Product.price <= max_price * 1.25)
        if query_text:
            q = q.filter(Product.name.ilike(f"%{query_text}%") | Product.description.ilike(f"%{query_text}%"))
        results = q.limit(30).all()
        return json.dumps([{
            "product_id": p.id, "name": p.name, "brand": p.brand, "category": p.category,
            "price": p.price, "rating": p.rating, "specs": p.specs, "merchant_id": p.merchant_id,
        } for p in results])
    finally:
        db.close()


@mcp.tool()
def get_product_details(product_id: str) -> str:
    """Get full details for a single product including merchant policies."""
    db = _db()
    try:
        p = db.query(Product).filter_by(id=product_id).first()
        if not p:
            return json.dumps({"error": "Product not found."})
        merchant = db.query(Merchant).filter_by(id=p.merchant_id).first() if p else None
        return json.dumps({
            "product_id": p.id, "name": p.name, "brand": p.brand, "category": p.category,
            "price": p.price, "description": p.description, "specs": p.specs,
            "rating": p.rating, "review_count": p.review_count, "warranty_months": p.warranty_months,
            "merchant": {
                "id": merchant.id if merchant else None,
                "name": merchant.name if merchant else None,
                "trust_score": merchant.trust_score if merchant else None,
                "negotiation_supported": merchant.negotiation_supported if merchant else False,
                "return_policy_days": merchant.return_policy_days if merchant else None,
            },
        })
    finally:
        db.close()


# ---------- INVENTORY ----------

@mcp.tool()
def check_stock(product_id: str) -> str:
    """Check available stock quantity for a product."""
    db = _db()
    try:
        inv = db.query(Inventory).filter_by(product_id=product_id).first()
        available = inv.available_qty if inv else 0
        return json.dumps({"product_id": product_id, "available_qty": available})
    finally:
        db.close()



@mcp.tool()
def reserve_inventory_tool(product_id: str, session_id: str, qty: int = 1) -> str:
    """Reserve inventory for a checkout attempt. Concurrency-safe. Expires in 5 minutes."""
    db = _db()
    try:
        try:
            res = reserve_inventory(db, product_id, session_id, qty)
            return json.dumps({"status": "RESERVED", "reservation_id": res.id, "expires_at": str(res.expires_at)})
        except ReservationError as e:
            return json.dumps({"status": "FAILED", "reason": str(e)})
    finally:
        db.close()


@mcp.tool()
def release_inventory_tool(reservation_id: str) -> str:
    """Release a reservation (payment failed / user abandoned)."""
    db = _db()
    try:
        release_inventory(db, reservation_id)
        return json.dumps({"status": "RELEASED"})
    finally:
        db.close()


@mcp.tool()
def compute_price_tool(product_id: str, negotiated_price: float = -1) -> str:
    """Compute the price for a product."""
    db = _db()
    try:
        p = db.query(Product).filter_by(id=product_id).first()
        if not p:
            return json.dumps({"error": "Product not found."})
        price = negotiated_price if (negotiated_price and negotiated_price > 0) else p.price
        return json.dumps({"base_price": p.price, "effective_price": price, "discount": 0.0})
    finally:
        db.close()





# ---------- NEGOTIATION ----------

@mcp.tool()
def get_negotiation_capability(product_id: str) -> str:
    """Check whether this product's merchant supports negotiation, and the floor discount %."""
    db = _db()
    try:
        p = db.query(Product).filter_by(id=product_id).first()
        merchant = db.query(Merchant).filter_by(id=p.merchant_id).first() if p else None
        return json.dumps({
            "negotiation_supported": merchant.negotiation_supported if merchant else True,
            "floor_discount_pct": merchant.negotiation_floor_pct if (merchant and merchant.negotiation_supported) else 0.10,
        })
    finally:
        db.close()


@mcp.tool()
def propose_offer(product_id: str, requested_price: float) -> str:
    """
    Propose a price to the merchant. Deterministic merchant-side rule logic (NOT an LLM):
    - If merchant doesn't negotiate, always rejected.
    - If requested discount is within the merchant's floor, accept.
    - Otherwise counter halfway between requested and floor.
    """
    db = _db()
    try:
        p = db.query(Product).filter_by(id=product_id).first()
        merchant = db.query(Merchant).filter_by(id=p.merchant_id).first() if p else None
        floor_pct = merchant.negotiation_floor_pct if (merchant and merchant.negotiation_supported) else 0.10
        price = p.price if p else round(requested_price / 0.90, 2)

        floor_price = round(price * (1 - floor_pct), 2)
        if requested_price >= floor_price:
            return json.dumps({"status": "ACCEPTED", "agreed_price": requested_price})

        counter = round((requested_price + floor_price) / 2, 2)
        counter = max(counter, floor_price)
        return json.dumps({
            "status": "COUNTER", "counter_price": counter, "floor_price": floor_price,
            "listed_price": price,
        })
    finally:
        db.close()



# ---------- CART & ORDERS ----------

@mcp.tool()
def create_cart(session_id: str) -> str:
    db = _db()
    try:
        cart = Cart(session_id=session_id, status="OPEN")
        db.add(cart)
        db.commit()
        return json.dumps({"cart_id": cart.id})
    finally:
        db.close()


@mcp.tool()
def add_to_cart(cart_id: str, product_id: str, qty: int, agreed_price: float) -> str:
    db = _db()
    try:
        item = CartItem(cart_id=cart_id, product_id=product_id, qty=qty, agreed_price=agreed_price)
        db.add(item)
        db.commit()
        return json.dumps({"cart_item_id": item.id})
    finally:
        db.close()


@mcp.tool()
def create_order_tool(cart_id: str, payment_id: str, total_amount: float) -> str:
    db = _db()
    try:
        cart = db.query(Cart).filter_by(id=cart_id).first()
        cart.status = "CHECKED_OUT"
        order = Order(cart_id=cart_id, payment_id=payment_id, total_amount=total_amount, status="CONFIRMED")
        db.add(order)
        db.commit()
        return json.dumps({"order_id": order.id, "status": order.status})
    finally:
        db.close()


@mcp.tool()
def get_order_status(order_id: str) -> str:
    db = _db()
    try:
        order = db.query(Order).filter_by(id=order_id).first()
        if not order:
            return json.dumps({"error": "NOT_FOUND"})
        return json.dumps({"order_id": order.id, "status": order.status, "total_amount": order.total_amount})
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
