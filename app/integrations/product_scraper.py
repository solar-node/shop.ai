"""
Live E-Commerce Scraper & Product Search Engine.
Supports live marketplace retrieval through configured SerpAPI and optional ScraperAPI.
"""
import os
import re
import urllib.parse
import requests

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(f):
            return f
        return decorator


@traceable(run_type="tool", name="Marketplace Search (SerpAPI / Google Shopping)")
def scrape_live_products(query: str, max_price: float = 0, max_results: int = 6) -> list[dict]:

    """
    Search live e-commerce marketplaces for real products, prices, ratings, review counts, and images.
    """
    results = []

    # Budget ceiling
    effective_max_price = max_price

    # ── 1. SerpAPI (Google Shopping India) ───────────────────────────────────
    serp_key = os.environ.get("SERPAPI_KEY", "")
    if serp_key:
        try:
            clean_q = query.strip()
            # If query does not mention India, append India for regional pricing
            search_q = f"{clean_q} India" if "india" not in clean_q.lower() else clean_q

            params = {
                "engine": "google_shopping",
                "q": search_q,
                "google_domain": "google.co.in",
                "gl": "in",
                "hl": "en",
                "api_key": serp_key,
            }
            resp = requests.get("https://serpapi.com/search.json", params=params, timeout=15)

            if resp.status_code == 200:
                raw_items = resp.json().get("shopping_results", [])
                
                for item in raw_items:
                    price = _clean_price(item.get("extracted_price") or item.get("price") or 0)
                    if effective_max_price > 0 and price > effective_max_price:
                        continue
                    if price <= 0:
                        continue
                    title = item.get("title", "")
                    old_price = _clean_price(item.get("extracted_old_price") or item.get("old_price") or 0)
                    discount_pct = round(((old_price - price) / old_price) * 100) if (old_price and old_price > price) else 0

                    raw_reviews = item.get("reviews") or item.get("review_count") or 0
                    reviews_count = _clean_review_count(raw_reviews)
                    rating = float(item.get("rating") or 0)

                    # Check for lowest seller across all buying options in the item
                    source_name = item.get("source") or item.get("merchant") or "Google Shopping"
                    sellers = item.get("sellers") or item.get("inline_sellers") or item.get("merchants") or []
                    for s in sellers:
                        s_price = _clean_price(s.get("price") or s.get("extracted_price") or 0)
                        s_name = s.get("name") or s.get("merchant") or s.get("source") or ""
                        if s_price > 0 and s_price < price:
                            price = s_price
                            if s_name:
                                source_name = s_name

                    delivery_info = item.get("delivery") or ""
                    badge = item.get("badge") or ""
                    
                    img = item.get("thumbnail") or item.get("thumbnail_url") or ""

                    results.append({
                        "product_id":   f"serp_{abs(hash(title)) % 1000000}",
                        "name":         title,
                        "price":        price,
                        "old_price":    old_price if (old_price and old_price > price) else None,
                        "discount_pct": discount_pct if discount_pct > 0 else None,
                        "image_url":    img,
                        "rating":       rating,
                        "review_count": reviews_count,
                        "flipkart_url": item.get("link") or item.get("product_link", ""),
                        "source":       source_name,
                        "delivery":     delivery_info,
                        "badge":        badge,
                        "specs":        {},
                        "available_qty": None,
                    })

                if results:
                    # Deduplicate by normalized title
                    deduped = {}
                    for item in results:
                        norm_key = re.sub(r'[^a-zA-Z0-9]', '', item["name"][:30].lower())
                        if norm_key not in deduped:
                            deduped[norm_key] = item
                        else:
                            existing = deduped[norm_key]
                            if item["price"] < existing["price"]:
                                deduped[norm_key] = item

                    final_list = list(deduped.values())

                    # Prioritize items in the target budget zone (>= 90% primary, >= 80% secondary)
                    if effective_max_price > 0:
                        def _budget_priority_key(x):
                            p = float(x.get("price") or 0)
                            ratio = p / effective_max_price
                            # Zone 4: >= 90% (e.g. > ₹9,000 for ₹10,000 budget)
                            # Zone 3: 80% - 90% (e.g. ₹8,000 - ₹9,000)
                            # Zone 2: 60% - 80%
                            # Zone 1: < 60% (e.g. ₹5,000 or cheap accessories)
                            zone_score = 4 if ratio >= 0.90 else (3 if ratio >= 0.80 else (2 if ratio >= 0.60 else 1))
                            return (zone_score, p, int(x.get("review_count") or 0))
                        final_list.sort(key=_budget_priority_key, reverse=True)

                    return final_list[:max_results]

        except Exception as e:
            print(f"[Scraper] SerpAPI error: {e}")


    # ── 2. Fallback ScraperAPI (Amazon.in) ───────────────────────────────────
    scraper_key = os.environ.get("SCRAPERAPI_KEY", "")
    if scraper_key:
        try:
            target_url = f"https://www.amazon.in/s?k={urllib.parse.quote(query)}"
            params = {
                "api_key": scraper_key,
                "url": target_url,
                "autoparse": "true",
                "country_code": "in",
            }
            resp = requests.get("https://api.scraperapi.com/structured/amazon/search", params=params, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", []):
                    price = _clean_price(item.get("price") or item.get("price_string") or 0)
                    if effective_max_price > 0 and price > effective_max_price:
                        continue
                    if price <= 0:
                        continue
                    title = item.get("name") or item.get("title", "")
                    rating = float(item.get("stars") or 0)
                    reviews_count = _clean_review_count(item.get("total_reviews") or 0)

                    results.append({
                        "product_id":   f"amz_{item.get('asin', abs(hash(title)) % 1000000)}",
                        "name":         title,
                        "price":        price,
                        "old_price":    None,
                        "discount_pct": None,
                        "image_url":    item.get("image", ""),
                        "rating":       rating,
                        "review_count": reviews_count,
                        "flipkart_url": item.get("url") or f"https://www.amazon.in/dp/{item.get('asin', '')}",
                        "source":       item.get("source") or "Amazon.in",
                        "delivery":     item.get("delivery", ""),
                        "badge":        item.get("badge", ""),
                        "specs":        {},
                        "available_qty": None,
                    })
                if results:
                    return results[:max_results]
        except Exception as e:
            print(f"[Scraper] ScraperAPI error: {e}")

    return results


def _clean_price(val) -> float:
    if isinstance(val, (int, float)):
        return round(float(val))
    cleaned = re.sub(r'[^\d.]', '', str(val))
    try:
        return round(float(cleaned))
    except ValueError:
        return 0.0


def _clean_review_count(val) -> int:
    if isinstance(val, int):
        return val
    s = str(val).lower().replace(",", "").replace("+", "").replace("reviews", "").replace("ratings", "").strip()
    try:
        if "k" in s:
            num = float(s.replace("k", ""))
            return int(num * 1000)
        return int(float(s))
    except Exception:
        return 0


