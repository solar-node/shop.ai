"""
Concurrency-safe inventory reservation.
Uses optimistic locking (version column) so two concurrent buyers competing for the
last unit resolve deterministically - one succeeds, one gets OUT_OF_STOCK (spec section 14).
"""
from datetime import datetime
from sqlalchemy import update

from database.models import Inventory, InventoryReservation


class ReservationError(Exception):
    pass


def reserve_inventory(db, product_id: str, session_id: str, qty: int = 1) -> InventoryReservation:
    """
    Atomic reserve: read version, attempt conditional update. If another transaction
    reserved concurrently, version won't match and we raise OUT_OF_STOCK.
    """
    inv = db.query(Inventory).filter_by(product_id=product_id).with_for_update(read=False).first()
    if inv is None:
        inv = Inventory(product_id=product_id, stock_qty=20, reserved_qty=0)
        db.add(inv)
        db.flush()


    if inv.available_qty < qty:
        raise ReservationError("OUT_OF_STOCK")

    current_version = inv.version
    result = db.execute(
        update(Inventory)
        .where(Inventory.id == inv.id, Inventory.version == current_version)
        .values(reserved_qty=Inventory.reserved_qty + qty, version=Inventory.version + 1)
    )
    if result.rowcount == 0:
        # Someone else updated it concurrently between our read and write
        db.rollback()
        raise ReservationError("OUT_OF_STOCK")

    reservation = InventoryReservation(
        product_id=product_id, session_id=session_id, qty=qty, status="ACTIVE"
    )
    db.add(reservation)
    db.commit()
    return reservation


def release_inventory(db, reservation_id: str):
    res = db.query(InventoryReservation).filter_by(id=reservation_id).first()
    if not res or res.status != "ACTIVE":
        return
    inv = db.query(Inventory).filter_by(product_id=res.product_id).first()
    inv.reserved_qty = max(0, inv.reserved_qty - res.qty)
    inv.version += 1
    res.status = "RELEASED"
    db.commit()


def confirm_reservation(db, reservation_id: str):
    """On successful payment: convert reservation into a permanent stock deduction."""
    res = db.query(InventoryReservation).filter_by(id=reservation_id).first()
    if not res or res.status != "ACTIVE":
        raise ReservationError("RESERVATION_NOT_ACTIVE")
    inv = db.query(Inventory).filter_by(product_id=res.product_id).first()
    inv.stock_qty -= res.qty
    inv.reserved_qty = max(0, inv.reserved_qty - res.qty)
    inv.version += 1
    res.status = "CONFIRMED"
    db.commit()


def expire_stale_reservations(db):
    """Should be called periodically (or lazily before each new reservation attempt)."""
    now = datetime.utcnow()
    stale = db.query(InventoryReservation).filter(
        InventoryReservation.status == "ACTIVE",
        InventoryReservation.expires_at < now,
    ).all()
    for res in stale:
        inv = db.query(Inventory).filter_by(product_id=res.product_id).first()
        if inv:
            inv.reserved_qty = max(0, inv.reserved_qty - res.qty)
            inv.version += 1
        res.status = "EXPIRED"
    db.commit()
    return len(stale)
