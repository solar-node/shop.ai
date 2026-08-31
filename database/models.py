"""
BudBuy database models.
SQLite for prototype (per spec section 34/40) - swap DATABASE_URL for Postgres later, same models work.
"""
from datetime import datetime, timedelta
import uuid
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import create_engine

Base = declarative_base()


def gen_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(String, primary_key=True, default=lambda: gen_id("mer"))
    name = Column(String, nullable=False)
    trust_score = Column(Float, default=0.9)  # 0-1, used by Risk Agent
    negotiation_supported = Column(Boolean, default=False)
    negotiation_floor_pct = Column(Float, default=0.10)  # max % off merchant will go to
    return_policy_days = Column(Integer, default=7)
    products = relationship("Product", back_populates="merchant")


class Product(Base):
    __tablename__ = "products"
    id = Column(String, primary_key=True, default=lambda: gen_id("prod"))
    merchant_id = Column(String, ForeignKey("merchants.id"))
    name = Column(String, nullable=False)
    brand = Column(String)
    category = Column(String, default="earbuds")  # earbuds, headphones, iem, speaker, dac, mic
    price = Column(Float, nullable=False)
    description = Column(Text)
    specs = Column(JSON)  # {battery_hours, anc, water_resistance, driver_size, ...}
    rating = Column(Float, default=4.0)
    review_count = Column(Integer, default=0)
    warranty_months = Column(Integer, default=12)

    merchant = relationship("Merchant", back_populates="products")
    inventory = relationship("Inventory", back_populates="product", uselist=False)
    offers = relationship("Offer", back_populates="product")


class Inventory(Base):
    __tablename__ = "inventory"
    id = Column(String, primary_key=True, default=lambda: gen_id("inv"))
    product_id = Column(String, ForeignKey("products.id"), unique=True)
    stock_qty = Column(Integer, default=10)
    reserved_qty = Column(Integer, default=0)  # held by active reservations
    version = Column(Integer, default=0)  # optimistic locking for concurrency

    product = relationship("Product", back_populates="inventory")

    @property
    def available_qty(self):
        return self.stock_qty - self.reserved_qty


class Offer(Base):
    __tablename__ = "offers"
    id = Column(String, primary_key=True, default=lambda: gen_id("off"))
    product_id = Column(String, ForeignKey("products.id"))
    offer_type = Column(String)  # coupon, payment_offer, bundle
    description = Column(String)
    discount_flat = Column(Float, default=0)
    discount_pct = Column(Float, default=0)
    min_order_value = Column(Float, default=0)
    active = Column(Boolean, default=True)

    product = relationship("Product", back_populates="offers")


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"
    id = Column(String, primary_key=True, default=lambda: gen_id("res"))
    product_id = Column(String, ForeignKey("products.id"))
    session_id = Column(String)
    qty = Column(Integer, default=1)
    status = Column(String, default="ACTIVE")  # ACTIVE, RELEASED, CONFIRMED, EXPIRED
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(minutes=5))


class Cart(Base):
    __tablename__ = "carts"
    id = Column(String, primary_key=True, default=lambda: gen_id("cart"))
    session_id = Column(String)
    status = Column(String, default="OPEN")  # OPEN, CHECKED_OUT, ABANDONED
    created_at = Column(DateTime, default=datetime.utcnow)
    items = relationship("CartItem", back_populates="cart")


class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(String, primary_key=True, default=lambda: gen_id("ci"))
    cart_id = Column(String, ForeignKey("carts.id"))
    product_id = Column(String, ForeignKey("products.id"))
    qty = Column(Integer, default=1)
    agreed_price = Column(Float)  # final negotiated/effective price
    cart = relationship("Cart", back_populates="items")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(String, primary_key=True, default=lambda: gen_id("pay"))
    cart_id = Column(String, ForeignKey("carts.id"))
    idempotency_key = Column(String, unique=True, index=True)  # session_id + cart_id
    razorpay_order_id = Column(String)
    razorpay_payment_id = Column(String, nullable=True)
    amount = Column(Float)
    status = Column(String, default="CREATED")  # CREATED, PENDING, SUCCESS, FAILED, UNKNOWN
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"
    id = Column(String, primary_key=True, default=lambda: gen_id("ord"))
    cart_id = Column(String, ForeignKey("carts.id"))
    payment_id = Column(String, ForeignKey("payments.id"))
    status = Column(String, default="CONFIRMED")
    total_amount = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentSession(Base):
    __tablename__ = "agent_sessions"
    id = Column(String, primary_key=True, default=lambda: gen_id("sess"))
    user_goal = Column(Text)
    state = Column(JSON)  # full BudBuyState snapshot
    status = Column(String, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentEvent(Base):
    """Decision ledger - one row per agent action, shown in UI (spec section 26)."""
    __tablename__ = "agent_events"
    id = Column(String, primary_key=True, default=lambda: gen_id("evt"))
    session_id = Column(String, index=True)
    agent = Column(String)  # ORCHESTRATOR, RESEARCH, DEAL, RISK, PURCHASE
    action = Column(String)
    detail = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)


DATABASE_URL = "sqlite:///budbuy.db"


def get_engine(url=DATABASE_URL):
    return create_engine(url, connect_args={"check_same_thread": False})


def get_session_factory(engine=None):
    engine = engine or get_engine()
    return sessionmaker(bind=engine)


def init_db(engine=None):
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    return engine
