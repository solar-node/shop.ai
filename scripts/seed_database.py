"""
Seeds the BudBuy DB with merchants (varying capabilities, per spec section 19)
and an audio-only product catalog (earbuds/headphones/IEMs/speakers), per spec section 32.
Run: python scripts/seed_database.py
"""
import sys, os, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database.models import (
    init_db, get_session_factory, Merchant, Product, Inventory, Offer
)

random.seed(42)

BRANDS = ["Sony", "SoundMax", "AudioX", "BassPro", "ClearTone", "Boat", "JBL", "Noise", "Skullcandy", "Realme"]
CATEGORIES = ["earbuds", "headphones", "iem", "speaker"]

ADJECTIVES = ["Pro", "Air", "Max", "Lite", "X", "Elite", "Wave", "Beat", "Flex", "Studio"]


def make_specs(category):
    return {
        "battery_hours": random.choice([4, 6, 8, 10, 12, 20, 30, 40]),
        "anc": random.random() < 0.4,
        "water_resistance": random.choice(["IPX4", "IPX5", "IPX7", None]),
        "driver_size_mm": random.choice([6, 8, 10, 12, 13]),
        "bluetooth_version": random.choice(["5.0", "5.1", "5.2", "5.3"]),
        "mic_quality": random.choice(["basic", "good", "excellent"]),
        "gym_suitable": random.random() < 0.5,
    }


def seed():
    engine = init_db()
    Session = get_session_factory(engine)
    db = Session()

    if db.query(Merchant).count() > 0:
        print("DB already seeded. Skipping.")
        return

    merchants = [
        Merchant(name="AudioBazaar", trust_score=0.95, negotiation_supported=False, return_policy_days=10),
        Merchant(name="DealHub Electronics", trust_score=0.88, negotiation_supported=True,
                  negotiation_floor_pct=0.12, return_policy_days=7),
        Merchant(name="SoundVerse", trust_score=0.9, negotiation_supported=True,
                  negotiation_floor_pct=0.08, return_policy_days=5),
        Merchant(name="QuickTech Store", trust_score=0.75, negotiation_supported=False, return_policy_days=3),
    ]
    db.add_all(merchants)
    db.flush()

    products = []
    for i in range(150):
        brand = random.choice(BRANDS)
        category = random.choice(CATEGORIES)
        adj = random.choice(ADJECTIVES)
        merchant = random.choice(merchants)
        price = round(random.uniform(499, 8999), -1) + random.choice([9, 99, 49])
        specs = make_specs(category)

        p = Product(
            merchant_id=merchant.id,
            name=f"{brand} {adj} {category.capitalize()} {i}",
            brand=brand,
            category=category,
            price=price,
            description=(
                f"{brand} {adj} {category} with {specs['battery_hours']}h battery, "
                f"{'ANC' if specs['anc'] else 'no ANC'}, "
                f"{specs['water_resistance'] or 'no water resistance'} rating, "
                f"{'great for gym use' if specs['gym_suitable'] else 'suited for daily/office use'}."
            ),
            specs=specs,
            rating=round(random.uniform(3.2, 4.9), 1),
            review_count=random.randint(5, 4000),
            warranty_months=random.choice([6, 12, 18, 24]),
        )
        products.append(p)
    db.add_all(products)
    db.flush()

    for p in products:
        inv = Inventory(product_id=p.id, stock_qty=random.randint(0, 25), reserved_qty=0)
        db.add(inv)

        if random.random() < 0.4:
            db.add(Offer(product_id=p.id, offer_type="coupon",
                          description="Flat discount coupon",
                          discount_flat=random.choice([100, 150, 200, 300]),
                          min_order_value=0))
        if random.random() < 0.3:
            db.add(Offer(product_id=p.id, offer_type="payment_offer",
                          description="Bank/UPI instant discount",
                          discount_pct=random.choice([5, 8, 10])))
        if random.random() < 0.15:
            db.add(Offer(product_id=p.id, offer_type="bundle",
                          description="Free carry case + extra ear tips bundle",
                          discount_flat=random.choice([150, 250, 300])))

    db.commit()
    print(f"Seeded {len(merchants)} merchants and {len(products)} products.")


if __name__ == "__main__":
    seed()
